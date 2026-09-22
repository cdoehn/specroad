"""Scoped field observations; not graph/lint execution or lifecycle permission."""
from .values import ProfileResource
from .errors import ProfileError
from ._contract import _fail, _pointer, KINDS
from ..model.artifact_schemas import MATURITIES
from ..model.canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object
from ..srx.errors import SrxError
from ..srx.pointers import resolve_tokens
from ..srx.types import MISSING
from ..srx._json_values import json_type
from ..srx.comparisons import compare

def _applies(entry, artifact):
    return (artifact["artifact_type"] in entry["artifact_types"]
            and (not entry["maturities"] or artifact.get("maturity") in entry["maturities"]))


def check_profile_fields(profile, artifact):
    """Check local fields only, without running lint or weakening Core schemas.

Presence and admissible values are independent: null is present, an absent
optional field is not rejected by allowed_values. Complete field types and
lifecycle/graph/policy checks remain the responsibility of their own layers.
"""
    if type(profile) is not ProfileResource:
        _fail("profile_resource_required")
    # Reuse the safe JCS value boundary; never invoke input conversion hooks.
    value = parse_json_object(canonical_json_bytes(artifact))
    if type(value.get("artifact_type")) is not str or value["artifact_type"] not in KINDS:
        _fail("profile_artifact_type_required", "/artifact_type")
    if type(value.get("maturity")) is not str or value["maturity"] not in MATURITIES:
        _fail("profile_invalid_maturity", "/maturity")
    diagnostics, checked = [], 0
    data = profile.data
    for group in ("required_fields", "forbidden_fields", "allowed_values"):
        for i, entry in enumerate(data[group]):
            if not _applies(entry, value):
                continue
            fields = [entry["field"]] if group == "allowed_values" else entry["fields"]
            for field in fields:
                at = "/" + group + "/" + str(i)
                try:
                    current = resolve_tokens(value, _pointer(field, at), rule_id="profile:field", at=at)
                except SrxError as error:
                    raise ProfileError("profile_field_access_error", pointer=at) from error
                checked += 1
                failed = ((group == "required_fields" and current is MISSING)
                          or (group == "forbidden_fields" and current is not MISSING))
                if group == "allowed_values" and current is not MISSING:
                    failed = not any(json_type(current) == json_type(allowed) and compare("eq", current, allowed, rule_id="profile:field")
                                     for allowed in entry["values"])
                if failed:
                    diagnostics.append({"reason": {"required_fields": "profile_required_field",
                        "forbidden_fields": "profile_forbidden_field", "allowed_values": "profile_value_not_allowed"}[group],
                        "severity": "error", "pointer": field, "profile_pointer": at})
    return {"profile": profile.binding(), "validation_scope": "profile_fields_only",
            "checked_fields": checked, "diagnostics": diagnostics,
            "field_checks_passed": not diagnostics, "profile_composition_checked": False,
            "relation_rules_checked": False, "lint_rules_checked": False, "approval_granted": False}
