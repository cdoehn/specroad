"""Shared read-only discard evidence and work-inventory contracts.

These helpers neither authorize recovery nor write records. Restart diagnosis
and locked completion use the same original/terminal binding and inventory.
"""
from ..model.canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object
from ._recovery_inputs import _parse
from ._recovery_evidence import EvidenceRecord, read_evidence
from ._recovery_work import work_file_inventory
from .receipt_values import transaction_receipt_path
from .recovery_values import RecoveryError, DiscardedJournal


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


def discard_work_inventory(journal, work):
    """Canonical intent inventory, retaining the original journal byte hash."""
    values = [{'path': 'journal.json', 'size': len(journal.source_bytes), 'sha256': journal.sha256}]
    values.extend(work_file_inventory(work))
    return sorted(values, key=lambda item: item['path'])


def verify_discard_inventory(journal, intent_value, work):
    if intent_value.get('work_files') != discard_work_inventory(journal, work):
        raise RecoveryError('recovery_discard_inventory_mismatch', exit_code=6)


def discard_work_location(files, prefix, archive, *, pending_marker):
    """Observe exactly one retained work location, without creating a directory."""
    with files.directory(prefix) as directory:
        active_work = directory is not None
    with files.directory(archive) as directory:
        archived_work = directory is not None
    if active_work == archived_work:
        raise RecoveryError('recovery_discard_work_unproven', exit_code=6)
    if pending_marker and not active_work:
        raise RecoveryError('recovery_discard_work_unproven', exit_code=6)
    return active_work, prefix if active_work else archive
