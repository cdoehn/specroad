"""Resume only a proved terminal discard, retaining its original audit event."""
import os
from hashlib import sha256

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..storage.json_syntax import parse_json_object
from ..security import paths as guards
from ._recovery_inputs import _parse, _unchanged_base, _work
from ._recovery_evidence import EvidenceRecord, read_evidence, persist_evidence, rollback_receipt
from ._recovery_receipts import existing_recovery_record, recheck_recovery_record
from ._recovery_barrier import barrier_record, persist_barrier, remove_barrier
from ._recovery_binding import check_discard_lock as _held
from ._recovery_work import work_file_inventory
from ._recovery_files import write_recovery_file, sync_recovery_file
from ._staging_files import _image
from .receipt_values import transaction_receipt_path
from .recovery_values import RecoveryError, RecoveryObservation, DiscardedJournal


def archived_discard(files, transaction_id):
    receipt = read_evidence(files, transaction_receipt_path(transaction_id))
    if receipt is None:
        raise RecoveryError('recovery_journal_missing', exit_code=5)
    value = parse_json_object(receipt.source_bytes)
    if value.get('format_version') != 'recovery-transaction-receipt-v1' or value.get('action') != 'discard':
        raise RecoveryError('discard_state_forbidden', exit_code=6)
    journal = _parse(canonical_json_bytes(value.get('journal')), transaction_id, files)
    if type(journal) is not DiscardedJournal or value.get('journal_sha256') != journal.sha256:
        raise RecoveryError('recovery_receipt_conflict', exit_code=6)
    return journal


def write_discard_file(directory, name, raw, **kwargs):
    """Publish only complete derivatives; retain named-file durability checks."""
    identity = write_recovery_file(directory, name, raw, **kwargs)
    sync_recovery_file(directory, name, identity, reason='recovery_discard_file_changed')
    _image(directory, name, len(raw), sha256(raw).hexdigest(), identity=identity)
    return identity


def pending_discard(files, journal):
    record = read_evidence(files, journal.path.rsplit('/', 1)[0] + '/journal.discard')
    if record is None:
        return None
    terminal = _parse(record.source_bytes, journal.data['transaction_id'], files, journal.data['project_id'])
    if type(terminal) is not DiscardedJournal:
        raise RecoveryError('recovery_discard_audit_mismatch', exit_code=6)
    original, _ = original_discard(files, terminal)
    if original.source_bytes != journal.source_bytes:
        raise RecoveryError('recovery_discard_audit_mismatch', exit_code=6)
    return terminal


def original_discard(files, terminal):
    """Bind terminal metadata to the entire original journal and immutable intent."""
    data = terminal.data
    audit_path = data['discard']['audit_path']
    original = read_evidence(files, audit_path + '/journal.before.json')
    intent = read_evidence(files, audit_path + '/intent.json')
    if (original is None or intent is None
            or original.sha256 != data['discard']['journal_before_sha256']
            or intent.sha256 != data['discard']['intent_sha256']):
        raise RecoveryError('recovery_discard_audit_mismatch', exit_code=6)
    journal = _parse(original.source_bytes, data['transaction_id'], files, data['project_id'])
    expected = journal.data
    expected.update(state='rolled_back', discard=data['discard'])
    value = parse_json_object(intent.source_bytes)
    fields = {'action': 'discard', 'phase': 'intent', 'format_version': 'recovery-audit-v1',
        'event_id': data['discard']['event_id'], 'transaction_id': data['transaction_id'],
        'project_id': data['project_id'], 'journal_sha256': journal.sha256,
        'previous_state': journal.data['state'], 'normative_writes': 0,
        'base_model_root_sha256': journal.data['base_model_root_sha256'],
        'target_model_root_sha256': journal.data['target_model_root_sha256']}
    if (journal.data['state'] not in ('building', 'prepared') or data != expected
            or data['discard']['previous_state'] != journal.data['state']
            or any(value.get(key) != item for key, item in fields.items())):
        raise RecoveryError('recovery_discard_audit_mismatch', exit_code=6)
    return journal, intent


def discard_completion_record(terminal, original, intent):
    data = terminal.data
    audit_path = data['discard']['audit_path']
    return EvidenceRecord(audit_path + '/completed.json', canonical_json_bytes({
        'format_version': 'recovery-audit-v1', 'event_id': data['discard']['event_id'],
        'phase': 'completed', 'action': 'discard', 'state': 'rolled_back',
        'transaction_id': data['transaction_id'], 'journal_before_sha256': original.sha256,
        'journal_sha256': terminal.sha256, 'intent_sha256': intent.sha256,
        'base_model_root_sha256': data['base_model_root_sha256'],
        'archive_path': audit_path + '/work', 'normative_writes': 0}))


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
    with files.directory(prefix) as directory:
        active_work = directory is not None
    with files.directory(archive) as directory:
        archived_work = directory is not None
    if active_work == archived_work:
        raise RecoveryError('recovery_discard_work_unproven', exit_code=6)
    if pending_marker and not active_work:
        raise RecoveryError('recovery_discard_work_unproven', exit_code=6)
    location = prefix if active_work else archive
    work_raw = journal.source_bytes if pending_marker else terminal.source_bytes
    pending_raw = terminal.source_bytes if pending_marker else None
    work = _work(files, journal, raw=work_raw, prefix=location, preflight=preflight, pending=pending_raw)
    expected_files = [{'path': 'journal.json', 'size': len(journal.source_bytes), 'sha256': journal.sha256}]
    expected_files.extend(work_file_inventory(work))
    if value.get('work_files') != sorted(expected_files, key=lambda item: item['path']):
        raise RecoveryError('recovery_discard_inventory_mismatch', exit_code=6)
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
