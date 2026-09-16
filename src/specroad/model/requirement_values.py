"""Owned requirement values, shared by new-draft construction and stored reads."""
from dataclasses import dataclass
import json

from .canonical import canonical_json_bytes
from .domain_fields import NormativeForce
from .domain_schemas import validate_domain_fields
from .errors import ModelError
from .language_tags import parse_language_tag
from .identity_values import RANDOM_SCHEME

VALIDATION_SCOPE = "requirement_fields_only"


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



@dataclass(frozen=True)
class RequirementMeaning:
    """No interpretation of natural language or evidence is implied."""
    language: str
    normative_force: NormativeForce
    statement: str

    def __post_init__(self):
        _explicit_text(self.language, "language")
        parse_language_tag(self.language)
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

