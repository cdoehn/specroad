"""Pure saved-plan preparation for the native working-Baseline facade."""
from ..authoring.plans import preview_authoring_request
from ..changes.baselines import prepare_baseline_operation


def prepare_working_baseline(model, *, baseline_id, name, actor, planned_at,
        change_plan_id, request_id=None, gates=(), strict=False):
    """Read-only preview with whole-project target validation and bound bytes."""
    operation = prepare_baseline_operation(model, baseline_id=baseline_id, name=name,
                                          actor=actor, planned_at=planned_at)
    return preview_authoring_request(model, 'baseline.create', [operation], actor=actor,
        planned_at=planned_at, change_plan_id=change_plan_id, request_id=request_id,
        gates=gates, strict=strict)
