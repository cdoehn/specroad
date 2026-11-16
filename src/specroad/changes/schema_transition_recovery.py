"""Compatibility imports for passive historical evidence; repair is unavailable."""
from .transition_history import (find_journal, completion_proof, historical_request,
    inspect_transition, takeover_evidence, status_transition, check_recovery_intent)
from .recovery_values import RecoveryError


def recover_transition(transaction_id, **options):
    raise RecoveryError('project_corrupted_manual_restore_required',
                        exit_code=5, mutation_possible=False)
