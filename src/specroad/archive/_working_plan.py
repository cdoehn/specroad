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
        configuration_id=None, release_id=None):
    """Select the existing working path or the closed Release-Baseline gate.

Release admission reads only the actual stored release. Supplied host gates
cannot replace the unavailable M13 readiness service or create a working plan
as a fallback for a release request.
"""
    if type(baseline_kind) is not str or baseline_kind not in ('working', 'release'):
        raise ModelError('baseline_kind_invalid')
    if baseline_kind == 'release':
        from .readiness import assess_release_baseline_readiness
        return assess_release_baseline_readiness(model, release_id=release_id).require_ready()
    if release_id is not None:
        raise ModelError('working_baseline_release_selection_not_applicable')
    return prepare_working_baseline(model, baseline_id=baseline_id, name=name,
        actor=actor, planned_at=planned_at, change_plan_id=change_plan_id,
        request_id=request_id, gates=gates, strict=strict, configuration_id=configuration_id)
