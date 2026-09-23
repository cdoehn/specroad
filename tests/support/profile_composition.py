"""Owned composition resources; not an approved project or resource provenance."""
from specroad.profiles import ProfileResource, compose_profiles
from .profiles import profile_data, encoded, selector


def profile(name="example", **changes):
    return ProfileResource(encoded(profile_data(profile_id=name, **changes)))


def composed(*profiles, **kwargs):
    core = kwargs.pop("core", None) or profile("core")
    keys = kwargs.pop("project_profiles", tuple(p.key for p in profiles))
    return compose_profiles([core, *profiles], core_key=core.key, project_profiles=keys, **kwargs)


def lint(rule_id="sample:lint", *, version="0.2.0", severity="warning", value=True):
    return {"rule_id": rule_id, "version": version, "artifact_types": ["requirement"],
            "maturities": [], "severity": severity,
            "program": {"language": "srx", "version": "1.0", "expression": {"op": "literal", "value": value}}}


def relation(rule_id="sample:relations", **changes):
    value = {"rule_id": rule_id, "version": "0.2.0", "artifact_types": ["requirement"],
             "maturities": [], "relation_types": ["verified_by"], "endpoint_types": ["test"],
             "minimum": 1, "direction": "outgoing", "severity": "warning"}
    value.update(changes)
    return value
