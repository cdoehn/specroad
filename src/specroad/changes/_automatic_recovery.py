"""Native automatic recovery, separate from the bounded start decision."""
from ..storage.operational_preflight import observe_operational_preflight
from .locking import project_lock, inspect_project_lock
from .recovery_lock import transaction_recovery_lock
from .recovery_values import RecoveryAuthority, RecoveryError, DiscardedJournal
from .recovery import (discard_unpublished_transaction, complete_published_transaction,
                       rollback_interrupted_transaction)
from .recovery_cleanup import cleanup_recovered_transaction
from .discard_preflight import prepare_discard_recovery
from ._lock_files import LockFiles
from ._recovery_inputs import _read_journal, _parse
from ._recovery_integrity import inspect_critical_inputs
from ._preflight_selection import selected_journal
from ._preflight_decision import RecoveryDecision


def recover_selected_transaction(decision: RecoveryDecision, data):
    """Populate actual recovery progress; never execute the new normal request.

    The caller retains this observation even if a later native step raises.
    Thus a verified partial completion is preserved by the public error boundary.
    Success still ends with code 5 and requires a separate normal invocation.
    """
    boundary, observed = decision.boundary, decision.observation
    config, transaction_id = decision.configuration, decision.transaction_id
    barrier, authority, actor = decision.barrier, decision.authority, decision.actor
    request_id, paths = decision.request_id, observed['unresolved_paths']
    current_policy = decision.check_policy
    # Full journal/resource diagnosis belongs to the explicitly selected
    # recovery phase, not the short transaction-metadata start check.
    data['phase'] = 'automatic_recovery'
    current_policy()
    if observe_operational_preflight(boundary) != observed:
        raise RecoveryError('preflight_operational_metadata_changed', exit_code=6)
    owner = inspect_project_lock(boundary.root, expected_project_id=config.project_id).data
    if owner['owner_state'] not in ('absent', 'dead'):
        data.update(reason='automatic_recovery_owner_unproven', owner_state=owner['owner_state'])
        return
    with LockFiles(boundary.root) as files:
        journal = selected_journal(files, transaction_id, config.project_id, barrier)
        if request_id == journal.data['request_id']:
            raise RecoveryError('preflight_request_id_conflicts_with_recovery', exit_code=6)
        integrity = inspect_critical_inputs(files, journal)
    if integrity['blockers']:
        raise RecoveryError(integrity['blockers'][0]['reason'], exit_code=6)
    decision = decision.for_transaction(journal)
    current_policy = decision.check_policy
    state = journal.data['state']
    discard = state in ('building', 'prepared') or type(journal) is DiscardedJournal
    command = 'recover discard' if discard else 'recover run'
    proof = (prepare_discard_recovery(boundary.root, transaction_id,
        expected_project_id=config.project_id, expected_journal_sha256=journal.sha256) if discard else None)
    options = dict(command=command, project_id=config.project_id,
                   request_id=journal.data['request_id'], transaction_id=transaction_id)

    guarded = RecoveryAuthority(authority.authority_id, authority.version, decision.authorize)
    if owner['owner_state'] == 'dead':
        lock = transaction_recovery_lock(boundary.root, **options,
            expected_lock_sha256=owner['record_sha256'], expected_journal_sha256=journal.sha256,
            authority=guarded, actor=actor, reason='Authorized preflight recovery', force=True)
    else:
        lock = project_lock(boundary.root, kind='recovery', **options)
    current_policy()
    data.update(recovery_attempted=True, mutation_possible=True)
    with lock as held:
        current_policy()
        held.check()
        if tuple(sorted(held._files.journal_entries())) != tuple(paths):
            raise RecoveryError('preflight_active_transactions_changed', exit_code=6)
        if selected_journal(held._files, transaction_id, config.project_id, barrier).source_bytes != journal.source_bytes:
            raise RecoveryError('recovery_journal_changed', exit_code=6)

        if discard:
            result = discard_unpublished_transaction(proof, transaction_id, held_lock=held,
                authority=guarded, actor=actor, reason='Authorized preflight recovery',
                expected_journal_sha256=journal.sha256).data
            cleanup = None
        elif barrier is not None:
            # The terminal marker and immutable intent select only cleanup;
            # the original work may already have moved to its bound archive.
            cleanup = cleanup_recovered_transaction(transaction_id, held_lock=held, authority=guarded,
                expected_journal_sha256=journal.sha256).data
            result = cleanup
        else:
            complete = state == 'committed' or (state == 'committing' and integrity['complete_target_verified'])
            action = complete_published_transaction if complete else rollback_interrupted_transaction
            result = action(transaction_id, held_lock=held, authority=guarded,
                            expected_journal_sha256=journal.sha256).data
            data['recovery'] = result
            terminal_raw, _ = _read_journal(held._files, transaction_id)
            terminal = _parse(terminal_raw, transaction_id, held._files, config.project_id)
            cleanup = cleanup_recovered_transaction(transaction_id, held_lock=held, authority=guarded,
                expected_journal_sha256=terminal.sha256).data
        data.update(recovery=result, cleanup=cleanup)
    after = observe_operational_preflight(boundary)
    data.update(exit_code=5, reason='recovery_completed_reinvoke', recovery_completed=True,
                recovery_required=after['consistency_state'] != 'consistent',
                requires_new_invocation=True, operational_after=after)
    return
