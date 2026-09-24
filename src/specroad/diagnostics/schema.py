"""Versioned machine projection schema shared with CLI contracts."""
from .values import FIELDS, LOCATION_KEYS, ORIGINS, SEVERITIES

def diagnostic_schema():
    """Shared serialized field contract, no external resolution or injected defaults."""
    nonempty = {"type": "string", "minLength": 1}
    nullable = lambda s: {"anyOf": [{"type": "null"}, s]}
    location = {"type": "object", "properties": {
        k: nullable({"type": "string", "pattern": r"^(?:$|/(?:[^~]|~[01])*$)"} if k == "pointer" else
                    {"type": "integer", "minimum": 0 if k.endswith("offset") else 1}) for k in LOCATION_KEYS},
        "additionalProperties": False}
    return {"type": "object", "properties": {
        **{k: dict(nonempty) for k in ("code", "category", "message")},
        "origin": {"enum": list(ORIGINS)}, "severity": {"enum": list(SEVERITIES)},
        **{k: nullable(dict(nonempty)) for k in ("rule_id", "artifact_id", "path", "rationale", "remediation")},
        "location": nullable(location), "related_ids": {"type": "array", "items": dict(nonempty)}},
        "required": sorted(FIELDS), "additionalProperties": False}
