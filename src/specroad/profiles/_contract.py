"""Pure closed profile-document validation. No discovery, imports from data or I/O."""
import re
from .errors import ProfileError
from ..model.errors import ModelError
from ..model.versions import SCHEMA_VERSION
from ..model.artifact_types import artifact_types
from ..model.artifact_schemas import MATURITIES
from ..model.canonical import canonical_json_bytes
from ..graph.relation_obligations import MinimumRelationRule
from ..srx.program import SrxProgram
from ..srx.errors import SrxError
from ..srx.pointers import parse_pointer

PROFILE_FORMAT = "profile-v1"
PROFILE_FIELDS = frozenset({"schema_version", "profile_format_version", "profile_id", "version",
    "required_fields", "forbidden_fields", "allowed_values", "relation_rules", "lint_rules", "severity_overrides"})
OPTIONAL_FIELDS = frozenset({"description", "hard_limits", "normative_policy"})
KINDS = frozenset(t.artifact_type for t in artifact_types())
SEVERITIES = frozenset({"error", "warning", "info"})
SEMVER = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?")
IDENTITY = re.compile(r"[A-Za-z][A-Za-z0-9._:-]{0,127}")

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
    _validate_composition_policies(value)
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


# Only known hard structure/format budgets belong in this merge. Soft work
# counters and query/display defaults are not made hard by putting them here.
HARD_LIMIT_FIELDS = frozenset({"artifact_file_bytes", "json_depth", "xml_depth",
    "srx_nodes", "srx_depth", "archive_uncompressed_bytes"})
_NON_PROFILE_POLICY = frozenset({"default_locale", "default_language", "language",
    "normative_language", "language_policy", "analyzer_policy", "srx_policy",
    "language_packages", "language_registry", "resource_limits", "work_targets",
    "generated_path", "auto_recover"})


def _validate_composition_policies(value):
    limits = value.get("hard_limits", {})
    if type(limits) is not dict:
        _fail("profile_object_required", "/hard_limits")
    for key, limit in limits.items():
        at = "/hard_limits/" + key.replace("~", "~0").replace("/", "~1")
        if key not in HARD_LIMIT_FIELDS:
            _fail("profile_not_a_hard_limit", at)
        if type(limit) is not int or limit < 1:
            _fail("profile_positive_hard_limit_required", at)
    policies = value.get("normative_policy", {})
    if type(policies) is not dict:
        _fail("profile_object_required", "/normative_policy")
    for key, scalar in policies.items():
        _identity(key, "/normative_policy")
        if key in _NON_PROFILE_POLICY or key.startswith("srx_"):
            _fail("profile_policy_belongs_to_project", "/normative_policy/" + key)
        if scalar is not None and type(scalar) not in (str, bool, int, float):
            _fail("profile_scalar_policy_required", "/normative_policy/" + key)
