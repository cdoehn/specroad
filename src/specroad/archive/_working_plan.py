"""Pure saved-plan preparation for the native working-Baseline facade."""
from ..authoring.plans import preview_authoring_request
from ..changes.baselines import prepare_baseline_operation
from ..model.errors import ModelError


def prepare_working_baseline(model, *, baseline_id, name, actor, planned_at,
        change_plan_id, request_id=None, gates=(), strict=False, configuration_id=None):
    """Read-only preview with whole-project target validation and bound bytes."""
    operation = prepare_baseline_operation(model, baseline_id=baseline_id, name=name,
        actor=actor, planned_at=planned_at, configuration_id=configuration_id)
    return preview_authoring_request(model, 'baseline.create', [operation], actor=actor,
        planned_at=planned_at, change_plan_id=change_plan_id, request_id=request_id,
        gates=gates, strict=strict)


def prepare_baseline_creation(model, *, baseline_kind, baseline_id, name, actor,
        planned_at, change_plan_id, request_id=None, gates=(), strict=False,
        configuration_id=None, release_id=None, evaluation=None,
        readiness_context=None, blocker_reviews=(), blocker_verifier=None):
    """Prepare the working path or a native, fully gated Release Baseline.

The Release path retains the whole-project snapshot and binds its separate
Release scope/selection. Supplied gates cannot substitute for native M13.
"""
    if type(baseline_kind) is not str or baseline_kind not in ('working', 'release'):
        raise ModelError('baseline_kind_invalid')
    if baseline_kind == 'release':
        from .readiness import assess_release_baseline_readiness
        checked = assess_release_baseline_readiness(model, release_id=release_id,
            evaluation=evaluation, readiness_context=readiness_context, gates=gates,
            blocker_reviews=blocker_reviews, blocker_verifier=blocker_verifier)
        fresh = checked.require_ready()
        if fresh.data['binding']['scope_descriptor']['configuration_id'] != configuration_id:
            # Readiness for one exact configuration cannot admit a differently
            # configured snapshot, even before target providers are assembled.
            raise ModelError('release_baseline_readiness_binding_mismatch')
        operation = prepare_baseline_operation(model, baseline_id=baseline_id, name=name,
            actor=actor, planned_at=planned_at, configuration_id=configuration_id, release_id=release_id)
        from ._release_gate import release_baseline_gates
        provided = release_baseline_gates(model, operation, readiness_context=readiness_context,
            gates=gates, blocker_reviews=blocker_reviews, blocker_verifier=blocker_verifier)
        return preview_authoring_request(model, 'baseline.create', [operation], actor=actor,
            planned_at=planned_at, change_plan_id=change_plan_id, request_id=request_id,
            gates=provided, strict=strict)
    if (release_id is not None or evaluation is not None or readiness_context is not None
            or blocker_reviews or blocker_verifier is not None):
        raise ModelError('working_baseline_release_selection_not_applicable')
    return prepare_working_baseline(model, baseline_id=baseline_id, name=name,
        actor=actor, planned_at=planned_at, change_plan_id=change_plan_id,
        request_id=request_id, gates=gates, strict=strict, configuration_id=configuration_id)
