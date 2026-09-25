"""Stable pure API: compose explicitly supplied values without performing writes."""
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..storage.json_syntax import parse_json_object
from ._common import _at
from .plan_contract import _validate_plan
from .values import ChangePlan, ChangeOperation

def prepare_change_plan(value):
    """Bind supplied plan values; never invent IDs, actor, time or target data.

    Caller supplies an unsigned data object. Existing self-hashes must be read
    with ChangePlan instead of silently being replaced with a recalculated hash.
    """
    encoded = _at("", canonical_json_bytes, value)
    owned = _at("", parse_json_object, encoded)
    _validate_plan(owned, hash_present=False)
    owned["change_plan_sha256"] = canonical_json_sha256(owned)
    return ChangePlan(canonical_json_bytes(owned))
