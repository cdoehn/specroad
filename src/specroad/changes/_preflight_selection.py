"""Select one native recovery without searching passive receipt/audit history."""
from ..storage.json_syntax import parse_json_object
from ._journal_codec import _transaction, _hash, journal_path
from ._recovery_barrier import barrier_path, barrier_record
from ._recovery_evidence import EvidenceRecord, evidence_root, read_evidence
from ._recovery_inputs import _parse
from ._recovery_terminal import read_terminal_journal
from ._discard_inputs import archived_discard
from .recovery_values import RecoveryError, DiscardedJournal, RolledBackJournal
from .receipt_values import CommittedJournal


def select_recovery(observed, project_id, boundary, read_metadata):
    """Bounded names plus at most one bounded native pending descriptor.

    This selects a candidate, not permission or proof of its terminal result.
    Full journal/intent/resource checks occur in the authorized recovery phase.
    """
    paths = observed['unresolved_paths']
    entries = {entry['path']: entry['directory'] for entry in observed['observed_entries']}
    journals = [p for p in paths if p.startswith('.specroad/transactions/') and entries[p]]
    barriers = [p for p in paths if p.startswith('.specroad/recovery/pending-') and not entries[p]]
    if len(journals) > 1 or len(barriers) > 1 or len(journals) + len(barriers) != len(paths):
        raise RecoveryError('explicit_recovery_selection_required', exit_code=5)
    selected = _transaction(journals[0].rsplit('/', 1)[-1]) if journals else None
    record = None
    if barriers:
        path = barriers[0]
        raw = read_metadata(path)
        value = parse_json_object(raw)
        fields = {'format_version', 'action', 'transaction_id', 'project_id',
                  'root_identity', 'journal_sha256', 'intent'}
        if (set(value) != fields or value.get('format_version') != 'terminal-recovery-pending-v1'
                or value.get('action') not in ('cleanup', 'discard')
                or value.get('project_id') != project_id
                or value.get('root_identity') != list(boundary._root_identity)
                or not _hash(value.get('journal_sha256'))):
            raise RecoveryError('preflight_recovery_barrier_unproven', exit_code=6)
        transaction = _transaction(value['transaction_id'])
        if (path != barrier_path(transaction, value['action'])
                or (selected is not None and selected != transaction)):
            raise RecoveryError('preflight_recovery_barrier_unproven', exit_code=6)
        record = EvidenceRecord(path, raw)
        selected = transaction
    if selected is None:
        raise RecoveryError('explicit_recovery_selection_required', exit_code=5)
    return selected, record


def selected_journal(files, transaction_id, project_id, barrier):
    """Exact canonical locations only; untrusted intent paths are never opened."""
    active = read_evidence(files, journal_path(transaction_id))
    action = None if barrier is None else parse_json_object(barrier.source_bytes)['action']
    if active is not None:
        journal = _parse(active.source_bytes, transaction_id, files, project_id)
    elif action == 'discard':
        journal = archived_discard(files, transaction_id)
    elif action == 'cleanup':
        journal = read_terminal_journal(files, transaction_id)
    else:
        raise RecoveryError('recovery_journal_missing', exit_code=5)
    if journal.data['project_id'] != project_id:
        raise RecoveryError('recovery_journal_binding_mismatch', exit_code=6)
    if barrier is not None:
        if action == 'discard' and type(journal) is DiscardedJournal:
            path = journal.data['discard']['audit_path'] + '/intent.json'
        elif action == 'cleanup' and type(journal) in (CommittedJournal, RolledBackJournal):
            path = evidence_root(transaction_id) + '/cleanup-' + journal.sha256 + '/intent.json'
        else:
            raise RecoveryError('preflight_recovery_barrier_unproven', exit_code=6)
        intent = read_evidence(files, path)
        actual = read_evidence(files, barrier.path)
        if (intent is None or actual != barrier
                or barrier_record(journal, intent, action).source_bytes != barrier.source_bytes):
            raise RecoveryError('preflight_recovery_barrier_unproven', exit_code=6)
    return journal
