"""Versioned passive profile contracts and field-only observations.

This layer owns profile bytes, validates declarations, and can observe their
local field constraints. It does not compose profiles, run lint/analyzers,
change artifact languages, or grant lifecycle/write permission.
"""
from dataclasses import dataclass
from hashlib import sha256
import re

from ..model.errors import ModelError
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.versions import SCHEMA_VERSION
from ..model.artifact_types import artifact_types
from ..model.artifact_schemas import MATURITIES
from ..storage.json_syntax import parse_json_object
from ..graph.relation_obligations import MinimumRelationRule
from ..srx.program import SrxProgram
from ..srx.errors import SrxError
from ..srx.pointers import parse_pointer, resolve_tokens
from ..srx.comparisons import compare
from ..srx.types import MISSING
from ..srx._json_values import json_type

PROFILE_FORMAT = "profile-v1"
PROFILE_FIELDS = frozenset({"schema_version", "profile_format_version", "profile_id", "version",
    "required_fields", "forbidden_fields", "allowed_values", "relation_rules", "lint_rules", "severity_overrides"})
OPTIONAL_FIELDS = frozenset({"description"})
KINDS = frozenset(t.artifact_type for t in artifact_types())
SEVERITIES = frozenset({"error", "warning", "info"})
SEMVER = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?")
IDENTITY = re.compile(r"[A-Za-z][A-Za-z0-9._:-]{0,127}")

class ProfileError(ModelError):
    """No source values or executable payloads are exposed in diagnostics."""


def _fail(reason, pointer=""):
    raise ProfileError(reason, pointer=pointer)


def _shape(value, fields, at, optional=frozenset()):
    if type(value) is not dict:
        _fail("profile_object_required", at)
    missing = set(fields) - value.keys()
    extra = value.keys() - set(fields) - set(optional)
    if missing:
        _fail("profile_missing_field", at + "/" + sorted(missing)[0])
    if extra:
        # Keys are already validated scalar strings by the strict JSON reader.
        key = sorted(extra)[0].replace("~", "~0").replace("/", "~1")
        _fail("profile_unknown_field", at + "/" + key)


def _identity(value, at):
    if type(value) is not str or IDENTITY.fullmatch(value) is None:
        _fail("profile_invalid_identity", at)
    return value


def _version(value, at):
    if type(value) is not str or SEMVER.fullmatch(value) is None:
        _fail("profile_exact_version_required", at)
    return value


def parse_profile_key(key):
    if type(key) is not str or key.count("@") != 1:
        _fail("profile_exact_key_required")
    name, version = key.split("@")
    return _identity(name, "/profile_id"), _version(version, "/version")


def _sequence(value, at):
    if type(value) is not list:
        _fail("profile_array_required", at)
    return value


def _tokens(value, allowed, at, *, nonempty=False):
    _sequence(value, at)
    if nonempty and not value:
        _fail("profile_empty_selector", at)
    if any(type(t) is not str or t not in allowed for t in value):
        _fail("profile_invalid_selector", at)
    if len(set(value)) != len(value):
        _fail("profile_duplicate_selector", at)


def _selector(value, at):
    _tokens(value["artifact_types"], KINDS, at + "/artifact_types", nonempty=True)
    _tokens(value["maturities"], MATURITIES, at + "/maturities")


def _pointer(value, at):
    try:
        tokens = parse_pointer(value, rule_id="profile:field", at=at)
    except SrxError as error:
        raise ProfileError("profile_invalid_pointer", pointer=at) from error
    if not tokens:
        _fail("profile_field_pointer_required", at)
    return tokens


def _severity(value, at):
    if type(value) is not str or value not in SEVERITIES:
        _fail("profile_invalid_severity", at)


def _rule_common(value, at):
    _identity(value["rule_id"], at + "/rule_id")
    _version(value["version"], at + "/version")
    _selector(value, at)
    _severity(value["severity"], at + "/severity")


def _validate_profile(value):
    _shape(value, PROFILE_FIELDS, "", OPTIONAL_FIELDS)
    if type(value["schema_version"]) is not str or value["schema_version"] != SCHEMA_VERSION:
        _fail("profile_unsupported_schema", "/schema_version")
    if type(value["profile_format_version"]) is not str or value["profile_format_version"] != PROFILE_FORMAT:
        _fail("profile_unsupported_format", "/profile_format_version")
    _identity(value["profile_id"], "/profile_id")
    _version(value["version"], "/version")
    if "description" in value and type(value["description"]) is not str:
        _fail("profile_description_string_required", "/description")
    for group in ("required_fields", "forbidden_fields"):
        for i, entry in enumerate(_sequence(value[group], "/" + group)):
            at = "/" + group + "/" + str(i)
            _shape(entry, {"artifact_types", "maturities", "fields"}, at)
            _selector(entry, at)
            fields = _sequence(entry["fields"], at + "/fields")
            if not fields:
                _fail("profile_empty_fields", at + "/fields")
            for j, field in enumerate(fields):
                _pointer(field, at + "/fields/" + str(j))
            if len(set(fields)) != len(fields):
                _fail("profile_duplicate_field", at + "/fields")
    for i, entry in enumerate(_sequence(value["allowed_values"], "/allowed_values")):
        at = "/allowed_values/" + str(i)
        _shape(entry, {"artifact_types", "maturities", "field", "values"}, at)
        _selector(entry, at)
        _pointer(entry["field"], at + "/field")
        values = _sequence(entry["values"], at + "/values")
        if not values:
            _fail("profile_empty_allowed_values", at + "/values")
        fingerprints = [canonical_json_bytes(v) for v in values]
        if len(set(fingerprints)) != len(fingerprints):
            _fail("profile_duplicate_allowed_value", at + "/values")
    for i, entry in enumerate(_sequence(value["relation_rules"], "/relation_rules")):
        at = "/relation_rules/" + str(i)
        _shape(entry, {"rule_id", "version", "artifact_types", "maturities", "relation_types",
                       "endpoint_types", "direction", "minimum", "severity"}, at)
        _rule_common(entry, at)
        try:
            MinimumRelationRule(**{k:v for k,v in entry.items() if k != "version"})
        except ModelError as error:
            raise ProfileError(error.reason, pointer=at + error.pointer) from error
    for i, entry in enumerate(_sequence(value["lint_rules"], "/lint_rules")):
        at = "/lint_rules/" + str(i)
        _shape(entry, {"rule_id", "version", "artifact_types", "maturities", "severity", "program"}, at)
        _rule_common(entry, at)
        try:
            SrxProgram(entry["program"], rule_id=entry["rule_id"])
        except SrxError as error:
            raise ProfileError("profile_invalid_srx", pointer=at + "/program" + error.pointer) from error
    identifiers = [r["rule_id"] for group in ("relation_rules", "lint_rules") for r in value[group]]
    if len(set(identifiers)) != len(identifiers):
        _fail("profile_duplicate_rule_identity")
    overrides = value["severity_overrides"]
    if type(overrides) is not dict:
        _fail("profile_object_required", "/severity_overrides")
    for key, severity in overrides.items():
        _identity(key, "/severity_overrides")
        _severity(severity, "/severity_overrides/" + key)


@dataclass(frozen=True, init=False)
class ProfileResource:
    """Own original bytes and canonical content identity, not trusted authorship."""
    source_bytes: bytes
    profile_id: str
    version: str
    sha256: str
    source_sha256: str

    def __init__(self, raw):
        if type(raw) is not bytes:
            _fail("profile_bytes_required")
        value = parse_json_object(raw)
        _validate_profile(value)
        object.__setattr__(self, "source_bytes", raw)
        object.__setattr__(self, "profile_id", value["profile_id"])
        object.__setattr__(self, "version", value["version"])
        object.__setattr__(self, "sha256", canonical_json_sha256(value))
        object.__setattr__(self, "source_sha256", sha256(raw).hexdigest())

    @property
    def key(self):
        return self.profile_id + "@" + self.version

    @property
    def data(self):
        return parse_json_object(self.source_bytes)

    def binding(self):
        return {"profile_id": self.profile_id, "version": self.version,
                "sha256": self.sha256, "hash_algorithm": "jcs-sha256",
                "profile_format_version": PROFILE_FORMAT}

    def rules(self, family):
        if type(family) is not str or family not in ("relation_rules", "lint_rules"):
            _fail("profile_rule_family_required")
        return tuple({"rule_id": r["rule_id"], "version": r["version"],
                      "sha256": canonical_json_sha256(r), "definition": r}
                     for r in self.data[family])

    def minimum_relation_rules(self):
        return tuple(MinimumRelationRule(**{k:v for k,v in r.items() if k != "version"})
                     for r in self.data["relation_rules"])


def resolve_profile(key, resources):
    """Exact selection from explicit already parsed resources; no CLI/defaults/I/O."""
    name, version = parse_profile_key(key)
    if type(resources) not in (list, tuple) or any(type(r) is not ProfileResource for r in resources):
        _fail("profile_resources_required")
    if len({r.key for r in resources}) != len(resources):
        _fail("profile_duplicate_resource")
    for resource in resources:
        if (resource.profile_id, resource.version) == (name, version):
            return resource
    _fail("profile_not_available")


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
    if "maturity" in value and (type(value["maturity"]) is not str or value["maturity"] not in MATURITIES):
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
