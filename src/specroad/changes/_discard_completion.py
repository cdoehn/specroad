"""Resume only a proved terminal discard, retaining its original audit event."""
import os
from hashlib import sha256

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..storage.json_syntax import parse_json_object
from ..security import paths as guards
from ._recovery_inputs import _unchanged_base, _work
from ._recovery_evidence import EvidenceRecord, persist_evidence, rollback_receipt
from ._recovery_receipts import existing_recovery_record, recheck_recovery_record
from ._recovery_barrier import barrier_record, persist_barrier, remove_barrier
from ._recovery_binding import check_discard_lock as _held
from ._recovery_files import write_recovery_file, sync_recovery_file
from ._staging_files import _image
from .recovery_values import RecoveryError, RecoveryObservation
from ._discard_inputs import (archived_discard, pending_discard, original_discard,
    discard_completion_record, verify_discard_inventory, discard_work_location)


def write_discard_file(directory, name, raw, **kwargs):
    """Publish only complete derivatives; retain named-file durability checks."""
    identity = write_recovery_file(directory, name, raw, **kwargs)
    sync_recovery_file(directory, name, identity, reason='recovery_discard_file_changed')
    _image(directory, name, len(raw), sha256(raw).hexdigest(), identity=identity)
    return identity


def _finish_discard(preflight, terminal, *, held_lock, authority, actor, reason,
                   expected_journal_sha256, attempted, authorized=False, pending_marker=False):
    files = held_lock._files
    data = terminal.data
    transaction_id = data['transaction_id']
    audit_path = data['discard']['audit_path']
    journal, intent = original_discard(files, terminal)
    original = EvidenceRecord(audit_path + '/journal.before.json', journal.source_bytes)
    if expected_journal_sha256 not in (terminal.sha256, journal.sha256):
        raise RecoveryError('recovery_journal_changed', exit_code=6)
    _held(held_lock, journal)
    base = _unchanged_base(preflight, journal, files)
    value = parse_json_object(intent.source_bytes)
    receipt = rollback_receipt(terminal, intent, action='discard')
    # Detect an existing conflict before adding any operational evidence.
    existing_recovery_record(files, receipt)
    selected = journal.path.rsplit('/', 1)[0]
    prefix, archive = tuple(selected.split('/')), tuple((audit_path + '/work').split('/'))
    active_work, location = discard_work_location(files, prefix, archive, pending_marker=pending_marker)
    work_raw = journal.source_bytes if pending_marker else terminal.source_bytes
    pending_raw = terminal.source_bytes if pending_marker else None
    work = _work(files, journal, raw=work_raw, prefix=location, preflight=preflight, pending=pending_raw)
    verify_discard_inventory(journal, value, work)
    tokens = [(record, existing_recovery_record(files, record)) for record in (original, intent)]
    active = files.journal_entries()

    def guard(expected_active, at):
        _held(held_lock, journal)
        if files.journal_entries() != expected_active:
            raise RecoveryError('recovery_active_set_changed', exit_code=6)
        if _unchanged_base(preflight, journal, files) != base:
            raise RecoveryError('recovery_base_changed', exit_code=6)
        if _work(files, journal, raw=work_raw, prefix=at, preflight=preflight, pending=pending_raw) != work:
            raise RecoveryError('recovery_work_changed', exit_code=6)
        for record, token in tokens:
            recheck_recovery_record(files, record, token)

    if not authorized:
        request = {'action': 'discard', 'transaction_id': transaction_id,
            'project_id': data['project_id'], 'actor': actor.as_fields(), 'reason': reason,
            'journal_sha256': terminal.sha256, 'original_journal_sha256': journal.sha256,
            'base_model_root_sha256': data['base_model_root_sha256'],
            'target_model_root_sha256': data['target_model_root_sha256']}
        raw = canonical_json_bytes(request)
        try:
            allowed = authority.check(request)
        except Exception as error:
            raise RecoveryError('recovery_authority_failed', exit_code=7) from error
        if type(allowed) is not bool or not allowed or canonical_json_bytes(request) != raw:
            raise RecoveryError('recovery_not_authorized', exit_code=7)
    guard(active, location)
    if pending_marker:
        attempted[0] = True
        with files.directory(prefix) as directory:
            identity = _image(directory, 'journal.discard', len(pending_raw), terminal.sha256)
            sync_recovery_file(directory, 'journal.discard', identity, reason='recovery_journal_changed')
            guard(active, location)
            os.replace('journal.discard', 'journal.json', src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
        work_raw, pending_raw = terminal.source_bytes, None
        work['journal.json'] = terminal.sha256
        guard(active, location)
    completion = discard_completion_record(terminal, journal, intent)
    completed = parse_json_object(completion.source_bytes)
    barrier = barrier_record(terminal, intent, 'discard')
    completion_token = existing_recovery_record(files, completion)
    barrier_token = existing_recovery_record(files, barrier)
    pending = active_work or completion_token is None or barrier_token is not None
    attempted[0] = True
    for record, _ in tokens:
        persist_evidence(files, record, write_new=write_discard_file)
    receipt_token = persist_evidence(files, receipt, write_new=write_discard_file)
    if pending:
        barrier_token, active = persist_barrier(files, barrier, active, write_new=write_discard_file)
    guard(active, location)
    recheck_recovery_record(files, receipt, receipt_token)
    with files.directory(tuple(audit_path.split('/'))) as audit:
        with files.directory(('.specroad', 'transactions')) as parent:
            if audit is None or parent is None:
                raise RecoveryError('recovery_discard_work_unproven', exit_code=6)
            if active_work:
                if (guards._identity(os.stat(transaction_id, dir_fd=parent, follow_symlinks=False)) != work['']
                        or 'work' in os.listdir(audit)):
                    raise RecoveryError('recovery_work_changed', exit_code=6)
                os.rename(transaction_id, 'work', src_dir_fd=parent, dst_dir_fd=audit)
            os.fsync(parent)
            os.fsync(audit)
    remaining = tuple(path for path in active if path != selected)
    guard(remaining, archive)
    completion_token = persist_evidence(files, completion, write_new=write_discard_file)
    guard(remaining, archive)
    recheck_recovery_record(files, receipt, receipt_token)
    recheck_recovery_record(files, completion, completion_token)
    if pending:
        remove_barrier(files, barrier, barrier_token)
        remaining = tuple(path for path in remaining if path != barrier.path)
        guard(remaining, archive)
    return RecoveryObservation._create({**completed, 'discard_completed': True,
        'receipt': receipt.reference, 'evidence_preserved': True, 'audit_path': audit_path,
        'model_loaded': False, 'remaining_active_paths': list(remaining),
        'write_authorized': False, 'atomic_snapshot': False})


def finish_discard(preflight, terminal, **kwargs):
    attempted = [False]
    try:
        return _finish_discard(preflight, terminal, attempted=attempted, **kwargs)
    except (OSError, SafetyViolation, ModelError) as error:
        if isinstance(error, RecoveryError):
            error.mutation_possible |= attempted[0]
            raise
        raise RecoveryError(getattr(error, 'reason', 'recovery_discard_completion_failed'),
            exit_code=getattr(error, 'exit_code', 5), mutation_possible=attempted[0]) from error
