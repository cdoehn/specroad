"""Native Baseline authoring with explicit host-owned identities and gates.

Preparation returns a saveable plan; execution never reallocates or silently
replans it. The trusted host supplies model/history, ID/time and semantic gates.
Release admission uses native M13; no command-line registration is implied.
"""
from ._working_plan import prepare_working_baseline, prepare_baseline_creation
from ..authoring.execution import apply_authoring_plan


def create_baseline(plan, model, *, transaction_id, authority, readiness_context=None,
        gates=(), blocker_reviews=(), blocker_verifier=None, strict=False, package_files=()):
    """Publish a saved Baseline through the ordinary native writer.

    Release publication needs the actual native context and fresh services,
    independently of the preview or saved plan. An observation is not authority.
    """
    from ..changes import ChangePlan
    from ..model.errors import ModelError
    if type(plan) is not ChangePlan:
        raise ModelError('typed_baseline_plan_required')
    owned = ChangePlan(plan.source_bytes)
    operations = owned.data['operations']
    if len(operations) != 1 or operations[0]['op'] != 'baseline_create':
        raise ModelError('baseline_operation_required')
    if operations[0]['record']['baseline_kind'] == 'release':
        from ._release_gate import release_baseline_gates
        gates = release_baseline_gates(model, operations[0], readiness_context=readiness_context,
            gates=gates, blocker_reviews=blocker_reviews, blocker_verifier=blocker_verifier)
    elif readiness_context is not None or blocker_reviews or blocker_verifier is not None:
        raise ModelError('working_baseline_release_selection_not_applicable')
    return apply_authoring_plan(owned, model, command_id='baseline.create',
        transaction_id=transaction_id, authority=authority, gates=gates,
        strict=strict, package_files=package_files)


def create_working_baseline(plan, model, *, transaction_id, authority,
        gates=(), strict=False, package_files=()):
    """Publish exactly the saved working plan with native lock/journal/receipt.

    Native failures preserve actual transaction state. A confirmed identical
    request replays its durable receipt without a second Baseline or object write.
    Every referenced object is staged before the sealed record is published.
    """
    return apply_authoring_plan(plan, model, command_id='baseline.create',
        transaction_id=transaction_id, authority=authority, gates=gates,
        strict=strict, package_files=package_files)
