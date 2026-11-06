"""Source-revalidated decisions over passive immutable resolution values."""
from ..model.canonical import canonical_json_bytes as jcs
from .conflict_schema import ROLES
from .field_values import _MISSING
from .conflicts import read_merge_conflicts
from .resolution_values import (MergeResolutions, parse_resolution_value,
    parse_merge_resolutions, parse_resolution_plan, _bound_plan, _prepare_resolution)


def read_merge_resolutions(raw, sources, *, history, expected_plan_sha256):
    """Revalidate the entire selected plan and all three native original sources."""
    plan = _bound_plan(raw, expected_plan_sha256)
    data = plan.data
    catalogue = data['catalogue'] if type(plan) is MergeResolutions else data
    read_merge_conflicts(jcs(catalogue), sources, history=history)
    return plan


def resolve_merge_conflict(raw, sources, *, history, expected_plan_sha256,
                          conflict_id, actor, resolved_at, take=None, value=_MISSING):
    """Append one locally checked decision only after native source revalidation."""
    result = _prepare_resolution(raw, expected_plan_sha256=expected_plan_sha256,
        conflict_id=conflict_id, actor=actor, resolved_at=resolved_at, take=take, value=value)
    read_merge_resolutions(raw, sources, history=history, expected_plan_sha256=expected_plan_sha256)
    for role in ROLES:
        verify_observation(getattr(sources, role))
    return result

from ._recorded import verify_observation
