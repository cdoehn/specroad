"""Explicit requirement construction, independent of prose and host settings.

This prepares a new draft in memory. It neither allocates/reserves its identity
nor writes a file, evaluates language policy, approves or verifies a requirement.
"""
from dataclasses import dataclass
from enum import Enum
import json

from .audit import Actor, UtcTimestamp, new_artifact_audit
from .canonical import canonical_json_bytes
from .configuration import ProjectConfiguration
from .domain_schemas import validate_domain_fields
from .errors import ModelError
from .identity_values import ArtifactIdentity, RANDOM_SCHEME
from .versions import SCHEMA_VERSION

_MISSING = object()
_RESERVED = frozenset({"schema_version", "artifact_type", "id", "id_scheme", "maturity",
                       "revision", "created_at", "updated_at", "created_by", "updated_by"})
VALIDATION_SCOPE = "requirement_fields_only"


class NormativeForce(str, Enum):
    """The declared force applies to the unchanged proposition, not its words."""
    MUST = "must"
    MUST_NOT = "must_not"
    SHOULD = "should"
    MAY = "may"

    @classmethod
    def from_value(cls, value):
        if type(value) is not str:
            raise ModelError("invalid_normative_force", pointer="/normative_force")
        try:
            return cls(value)
        except ValueError as error:
            raise ModelError("invalid_normative_force", pointer="/normative_force") from error


def _owned(value):
    # Validate exact JSON values before serializing. No object conversion hook,
    # detector, clock, locale, network, file or shell adapter participates.
    canonical_json_bytes(value)
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except RecursionError as error:
        raise ModelError("unsupported_json_nesting") from error


def _explicit_text(value, name):
    if type(value) is not str or not value.strip() or "\0" in value:
        raise ModelError("invalid_requirement_text", pointer="/" + name)
    return value


def _resolve(data, field, argument, default=_MISSING):
    """Reject conflicting supplied values; absence, null and empty are distinct."""
    if argument is not _MISSING:
        if field in data and (type(data[field]) is not type(argument) or data[field] != argument):
            raise ModelError("requirement_input_conflict", pointer="/" + field)
        data[field] = argument
        return "argument"
    if field in data:
        return "input"
    if default is not _MISSING:
        data[field] = default
        return "project_default"
    raise ModelError("missing_field", pointer="/" + field)


@dataclass(frozen=True)
class RequirementMeaning:
    """No interpretation of natural language or evidence is implied."""
    language: str
    normative_force: NormativeForce
    statement: str

    def __post_init__(self):
        _explicit_text(self.language, "language")
        _explicit_text(self.statement, "statement")
        if type(self.normative_force) is not NormativeForce:
            raise ModelError("typed_normative_force_required", pointer="/normative_force")


def requirement_meaning(value):
    """Read a valid requirement's explicit tuple without inferring its intent."""
    validate_domain_fields(value, expected_type="requirement")
    return RequirementMeaning(value["language"], NormativeForce.from_value(value["normative_force"]),
                              value["statement"])


@dataclass(frozen=True, init=False)
class RequirementDraft:
    """Owned preparation, not a Change Plan, storage permission or reserved ID."""
    _encoded: bytes
    language_source: str
    force_source: str
    validation_scope: str

    def __init__(self, value, *, language_source, force_source):
        data = _owned(value)
        validate_domain_fields(data, expected_type="requirement")
        if data["maturity"] != "draft" or data["revision"] != 1 or data["id_scheme"] != RANDOM_SCHEME:
            raise ModelError("new_requirement_draft_required")
        if (data["created_at"] != data["updated_at"] or data["created_by"] != data["updated_by"]):
            raise ModelError("new_requirement_audit_required")
        if language_source not in ("input", "argument", "project_default") or force_source not in ("input", "argument"):
            raise ModelError("invalid_requirement_input_source")
        object.__setattr__(self, "_encoded", json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8"))
        object.__setattr__(self, "language_source", language_source)
        object.__setattr__(self, "force_source", force_source)
        object.__setattr__(self, "validation_scope", VALIDATION_SCOPE)

    @property
    def data(self):
        return json.loads(self._encoded)

    @property
    def meaning(self):
        return requirement_meaning(self.data)


def prepare_requirement(fields, *, identity, actor, planned_at, configuration=None,
                        language=_MISSING, normative_force=_MISSING):
    """Materialize an explicitly described new requirement, always as a draft.

    fields is the input object's content (without identity/audit/maturity).
    language/normative_force are independent explicitly supplied command inputs.
    Only configuration.language_policy.default_language can fill absent language.
    A later writer must still bind configuration, reserve the ID and authorize.
    """
    if type(fields) is not dict:
        raise ModelError("object_required")
    data = _owned(fields)
    forbidden = sorted(data.keys() & _RESERVED)
    if forbidden:
        raise ModelError("reserved_requirement_field", pointer="/" + forbidden[0])
    if type(identity) is not ArtifactIdentity or identity.artifact_type != "requirement" or identity.id_scheme != RANDOM_SCHEME:
        raise ModelError("new_requirement_identity_required")
    if configuration is not None and type(configuration) is not ProjectConfiguration:
        raise ModelError("typed_project_configuration_required")
    default = _MISSING
    if configuration is not None:
        if identity.id_prefix != configuration.id_prefix:
            raise ModelError("requirement_project_prefix_mismatch")
        default = configuration.data.get("language_policy", {}).get("default_language", _MISSING)
    language_source = _resolve(data, "language", language, default)
    force_source = _resolve(data, "normative_force", normative_force)
    _explicit_text(data["language"], "language")
    NormativeForce.from_value(data["normative_force"])
    data.update(schema_version=SCHEMA_VERSION, artifact_type="requirement", id=identity.id,
                id_scheme=identity.id_scheme, maturity="draft")
    data.update(new_artifact_audit(actor=actor, planned_at=planned_at).as_fields())
    data.setdefault("relations", [])
    data.setdefault("extensions", {})
    data.setdefault("implementation_status", "not_started")
    data.setdefault("verification_plan_status", "not_planned")
    return RequirementDraft(data, language_source=language_source, force_source=force_source)
