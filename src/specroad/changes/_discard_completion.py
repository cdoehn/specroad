"""Resume only a proved terminal discard, retaining its original audit event."""
import os

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..storage.json_syntax import parse_json_object
from ..security import paths as guards
from ._recovery_inputs import _parse, _unchanged_base, _work
from ._recovery_evidence import EvidenceRecord, read_evidence, persist_evidence, rollback_receipt
from ._recovery_receipts import existing_recovery_record, recheck_recovery_record
from ._recovery_barrier import barrier_record, remove_barrier
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


def _finish_discard(preflight, terminal, *, held_lock, authority, actor, reason,
                   expected_journal_sha256, attempted, authorized=False):
    from .recovery import _held
    files = held_lock._files
    data = terminal.data
    transaction_id = data['transaction_id']
    audit_path = data['discard']['audit_path']
    original = read_evidence(files, audit_path + '/journal.before.json')
    intent = read_evidence(files, audit_path + '/intent.json')
    if (original is None or intent is None
            or original.sha256 != data['discard']['journal_before_sha256']
            or intent.sha256 != data['discard']['intent_sha256']):
        raise RecoveryError('recovery_discard_audit_mismatch', exit_code=6)
    journal = _parse(original.source_bytes, transaction_id, files)
    if expected_journal_sha256 not in (terminal.sha256, journal.sha256):
        raise RecoveryError('recovery_journal_changed', exit_code=6)
    _held(held_lock, journal)
    base = _unchanged_base(preflight, journal, files)
    value = parse_json_object(intent.source_bytes)
    if (value.get('action') != 'discard' or value.get('phase') != 'intent'
            or value.get('event_id') != data['discard']['event_id']
            or value.get('transaction_id') != transaction_id
            or value.get('journal_sha256') != journal.sha256
            or value.get('previous_state') != journal.data['state']
            or value.get('base_model_root_sha256') != journal.data['base_model_root_sha256']):
        raise RecoveryError('recovery_discard_audit_mismatch', exit_code=6)
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
    location = prefix if active_work else archive
    work = _work(files, journal, raw=terminal.source_bytes, prefix=location, preflight=preflight)
    expected_files = [{'path': 'journal.json', 'size': len(journal.source_bytes), 'sha256': journal.sha256}]
    expected_files.extend({'path': path, 'size': token['size'], 'sha256': token['sha256']}
                          for path, token in sorted(work.items()) if type(token) is dict)
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
        if _work(files, journal, raw=terminal.source_bytes, prefix=at, preflight=preflight) != work:
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
    completed = {'format_version': 'recovery-audit-v1', 'event_id': data['discard']['event_id'],
        'phase': 'completed', 'action': 'discard', 'state': 'rolled_back',
        'transaction_id': transaction_id, 'journal_before_sha256': journal.sha256,
        'journal_sha256': terminal.sha256, 'intent_sha256': intent.sha256,
        'base_model_root_sha256': data['base_model_root_sha256'],
        'archive_path': audit_path + '/work', 'normative_writes': 0}
    completion = EvidenceRecord(audit_path + '/completed.json', canonical_json_bytes(completed))
    barrier = barrier_record(terminal, intent, 'discard')
    completion_token = existing_recovery_record(files, completion)
    barrier_token = existing_recovery_record(files, barrier)
    pending = active_work or completion_token is None or barrier_token is not None
    attempted[0] = True
    for record, _ in tokens:
        persist_evidence(files, record)
    receipt_token = persist_evidence(files, receipt)
    if pending:
        barrier_token = persist_evidence(files, barrier)
        observed_active = files.journal_entries()
        if set(observed_active) != set(active) | {barrier.path}:
            raise RecoveryError('recovery_active_set_changed', exit_code=6)
        active = observed_active
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
    completion_token = persist_evidence(files, completion)
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
