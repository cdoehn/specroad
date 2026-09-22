"""Owned profile fixtures; no project defaults or environmental discovery."""
import json
from .artifacts import common_artifact

def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

def profile_data(**changes):
    data = {"schema_version": "0.2.0", "profile_format_version": "profile-v1",
            "profile_id": "sample", "version": "0.2.0", "required_fields": [],
            "forbidden_fields": [], "allowed_values": [], "relation_rules": [],
            "lint_rules": [], "severity_overrides": {}}
    data.update(changes)
    return data

def selector(**changes):
    data = {"artifact_types": ["requirement"], "maturities": []}
    data.update(changes)
    return data

def requirement(**changes):
    value = common_artifact("requirement", "REQ", requirement_kind="functional",
            normative_force="may", statement="Keep UTF-8 日本語 e\u0301 العربية", priority="low",
            criticality="normal", implementation_status="not_started", verification_plan_status="not_planned")
    value.update(changes)
    return value
