"""Reusable immutable-by-construction field schema factories for Core records.

Every call returns owned JSON values. Field schemas describe data; none load
project plugins, interpret prose, resolve graph edges or authorize a write.
"""

IMPLEMENTATION_STATUSES = ("not_started", "in_progress", "implemented", "blocked", "not_applicable")
VERIFICATION_PLAN_STATUSES = ("not_planned", "planned", "running", "waived", "not_applicable")
REQUIREMENT_KINDS = ("functional", "quality", "interface", "data", "constraint", "security", "safety", "compliance")
PRIORITIES = ("mandatory", "high", "medium", "low")
CRITICALITIES = ("normal", "important", "critical", "safety_critical")
from enum import Enum
from .errors import ModelError


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


NORMATIVE_FORCES = tuple(item.value for item in NormativeForce)


def approved_required_fields(kind):
    """Instance-local maturity obligations shared by schema and lint readers."""
    return {
        "goal": ("success_criterion",), "need": ("rationale", "priority"),
        "capability": ("outcome", "priority"), "requirement": ("rationale",),
        "scenario": ("preconditions", "postconditions", "exceptions"),
        "decision": ("alternatives", "consequences"),
        "assumption": ("validation_method", "reevaluation_condition"),
        "release": ("scope_descriptor",), "milestone": ("done_criteria",),
    }.get(kind, ())


def reference_schema(prefix):
    # Reading permits both current and preserved legacy identities. Generating
    # new identifiers and resolving graph targets belong to their later services.
    return {"type": "string", "pattern": r"^[A-Z][A-Z0-9]{1,7}-" + prefix +
            r"-(?:[0-7][0-9A-HJKMNP-TV-Z]{25}|[0-9]{4})(?![\s\S])"}


def field_schemas():
    text = {"$ref": "#/$defs/text"}
    owner = {"anyOf": [text, {"$ref": "#/$defs/actor"}]}
    texts = {"type": "array", "items": text}
    criteria = {"type": "array", "minItems": 1, "items": text}
    implementation = {"enum": list(IMPLEMENTATION_STATUSES)}
    verification = {"enum": list(VERIFICATION_PLAN_STATUSES)}
    priority = {"enum": list(PRIORITIES)}
    detail = {"anyOf": [text, {"type": "object", "not": {"const": {}}}]}
    # No risk/assumption vocabulary is enumerated in spec 9.4. Store nonempty
    # labels without inventing meanings or treating a label as proof of success.
    assessment = {"anyOf": [text, {"type": "number", "minimum": 0}]}
    waiver = {
        "type": "object", "required": ["reason", "scope_descriptor", "expiry_condition", "human_review_id", "artifact_sha256"],
        "properties": {"reason": text, "scope_descriptor": {"type": "object"}, "expiry_condition": text,
                       "human_review_id": text,
                       "artifact_sha256": {"type": "string", "pattern": r"^[0-9a-f]{64}(?![\s\S])"},
                       "configuration_sha256": {"anyOf": [{"type": "null"}, {"type": "string", "pattern": r"^[0-9a-f]{64}(?![\s\S])"}]}},
        "additionalProperties": False,
    }
    return {
        "text": text, "owner": owner, "texts": texts, "criteria": criteria,
        "implementation": implementation, "verification": verification,
        "priority": priority, "detail": detail, "assessment": assessment,
        "waiver": waiver,
    }
