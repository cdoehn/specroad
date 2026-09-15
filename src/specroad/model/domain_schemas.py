"""Read-only field contracts for the thirteen domain and planning artifact types.

These contracts extend the common envelope. They do not evaluate a project's
relations, profiles, language registry, evidence, review or release readiness.
A parsed record is never an authorization to create, approve or publish data.
"""

from ._schema import validate_builtin
from .artifact_schemas import artifact_common_schema, validate_common_fields
from .artifact_types import artifact_type
from .errors import ModelError
from .versions import SCHEMA_VERSION


DOMAIN_TYPES = (
    "goal", "need", "capability", "requirement", "scenario", "decision",
    "risk", "assumption", "component", "interface", "release", "milestone", "task",
)
VALIDATION_SCOPE = "domain_fields_only"
IMPLEMENTATION_STATUSES = ("not_started", "in_progress", "implemented", "blocked", "not_applicable")
VERIFICATION_PLAN_STATUSES = ("not_planned", "planned", "running", "waived", "not_applicable")
REQUIREMENT_KINDS = ("functional", "quality", "interface", "data", "constraint", "security", "safety", "compliance")
PRIORITIES = ("mandatory", "high", "medium", "low")
CRITICALITIES = ("normal", "important", "critical", "safety_critical")
NORMATIVE_FORCES = ("must", "must_not", "should", "may")


def _reference(prefix):
    # Reading permits both current and preserved legacy identities. Generating
    # new identifiers and resolving graph targets belong to their later services.
    return {"type": "string", "pattern": r"^[A-Z][A-Z0-9]{1,7}-" + prefix +
            r"-(?:[0-7][0-9A-HJKMNP-TV-Z]{25}|[0-9]{4})(?![\s\S])"}


def _type_fields(kind):
    """Return independent trusted data, not user-configurable executable rules."""
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
    fields = {
        "goal": (("statement", "owner"), {"statement": text, "owner": owner,
                  "success_criterion": {"anyOf": [text, criteria]}}),
        "need": (("stakeholder", "statement", "owner"), {"stakeholder": owner,
                  "statement": text, "owner": owner, "rationale": text, "priority": priority}),
        "capability": (("description", "owner", "implementation_status", "verification_plan_status"),
                       {"description": text, "owner": owner, "implementation_status": implementation,
                        "verification_plan_status": verification, "outcome": text, "priority": priority}),
        "requirement": (("requirement_kind", "language", "normative_force", "statement", "priority",
                         "criticality", "implementation_status", "verification_plan_status"),
                        {"requirement_kind": {"enum": list(REQUIREMENT_KINDS)}, "normative_force": {"enum": list(NORMATIVE_FORCES)},
                         "statement": text, "priority": priority, "criticality": {"enum": list(CRITICALITIES)},
                         "implementation_status": implementation, "verification_plan_status": verification,
                         "rationale": text, "deviation_conditions": text, "deviation_authority": owner,
                         # Structured semantics are preserved, not evaluated as SRX, code or natural language.
                         "scope": detail, "actor": owner, "trigger": detail, "preconditions": texts,
                         "response": detail, "object": detail, "timing": detail,
                         "thresholds": {"type": "array", "items": {"type": "object"}}, "exceptions": texts}),
        "scenario": (("actors", "trigger", "main_flow"),
                     {"actors": {"type": "array", "minItems": 1, "items": owner}, "trigger": text,
                      "main_flow": criteria, "preconditions": texts, "postconditions": texts, "exceptions": texts}),
        "decision": (("context", "decision", "rationale", "owner"),
                     {"context": text, "decision": text, "rationale": text, "owner": owner,
                      "alternatives": texts, "consequences": texts}),
        "risk": (("description", "probability", "impact", "risk_status", "owner"),
                 {"description": text, "probability": {"anyOf": [text, {"type": "number", "minimum": 0, "maximum": 1}]},
                  "impact": assessment, "risk_status": text, "owner": owner, "acceptance_rationale": text}),
        "assumption": (("statement", "validation_status", "owner"),
                       {"statement": text, "validation_status": text, "owner": owner,
                        "validation_method": text, "reevaluation_condition": text}),
        "component": (("description", "responsibility", "owner", "implementation_status"),
                      {"description": text, "responsibility": text, "owner": owner, "implementation_status": implementation}),
        "interface": (("description", "source_component", "target_component", "owner", "implementation_status"),
                      {"description": text, "source_component": _reference("COMP"), "target_component": _reference("COMP"),
                       "owner": owner, "implementation_status": implementation,
                       "contract": detail, "contract_not_applicable": text}),
        "release": (("name", "objective", "readiness_policy"),
                    {"name": text, "objective": text, "readiness_policy": {"type": "object"},
                     "target_date": {"type": "string", "format": "date"}, "scope_descriptor": {"type": "object"}}),
        "milestone": (("objective", "owner"), {"objective": text, "owner": owner, "done_criteria": criteria}),
        "task": (("description", "owner", "implementation_status", "verification_plan_status", "done_criteria"),
                 {"description": text, "owner": owner, "implementation_status": implementation,
                  "verification_plan_status": verification, "done_criteria": criteria}),
    }
    required, properties = fields[kind]
    if "verification_plan_status" in properties:
        properties["verification_waiver"] = {
            "type": "object", "required": ["reason", "scope_descriptor", "expiry_condition", "human_review_id", "artifact_sha256"],
            "properties": {"reason": text, "scope_descriptor": {"type": "object"}, "expiry_condition": text,
                           "human_review_id": text,
                           "artifact_sha256": {"type": "string", "pattern": r"^[0-9a-f]{64}(?![\s\S])"},
                           "configuration_sha256": {"anyOf": [{"type": "null"}, {"type": "string", "pattern": r"^[0-9a-f]{64}(?![\s\S])"}]}},
            "additionalProperties": False,
        }
    return required, properties


def _required_when(field, value, names):
    return {"anyOf": [{"properties": {field: {"not": {"const": value}}}}, {"required": list(names)}]}


def domain_schema(kind, version=SCHEMA_VERSION):
    """Return a detached built-in schema for the implemented read-only layer."""
    schema = artifact_common_schema(kind, version)
    if kind not in DOMAIN_TYPES:
        raise ModelError("domain_type_not_supported", pointer="/artifact_type")
    required, fields = _type_fields(kind)
    schema["$id"] = "urn:specroad:schema:" + version + ":artifact-domain:" + kind
    schema["$comment"] = "Domain fields only; graph, profile, evidence and authorization gates are not evaluated."
    schema["x-specroad-validation-scope"] = VALIDATION_SCOPE
    schema["required"] = list(dict.fromkeys([*schema["required"], *required]))
    schema["properties"].update(fields)
    schema["additionalProperties"] = False
    conditions = []
    if kind == "requirement":
        conditions.append(_required_when("normative_force", "should", ("deviation_conditions", "deviation_authority")))
    if "verification_plan_status" in fields:
        conditions.append(_required_when("verification_plan_status", "waived", ("verification_waiver",)))
    # Only instance-local mandatory data are checked here. For example, a
    # risk's mitigation and a task's implementation link may be INCOMING edges;
    # their absence cannot be decided from this file alone.
    approved_fields = {
        "goal": ("success_criterion",), "need": ("rationale", "priority"),
        "capability": ("outcome", "priority"), "requirement": ("rationale",),
        "scenario": ("preconditions", "postconditions", "exceptions"),
        "decision": ("alternatives", "consequences"),
        "assumption": ("validation_method", "reevaluation_condition"),
        "release": ("scope_descriptor",), "milestone": ("done_criteria",),
    }
    if kind in approved_fields:
        conditions.append(_required_when("maturity", "approved", approved_fields[kind]))
    if kind == "interface":
        conditions.append({"anyOf": [
            {"properties": {"maturity": {"not": {"const": "approved"}}}},
            {"required": ["contract"]}, {"required": ["contract_not_applicable"]},
        ]})
    schema["allOf"] = conditions
    return schema


def _milestone_release(value):
    relations = [relation for relation in value["relations"] if relation.get("type") == "part_of"]
    if len(relations) != 1:
        raise ModelError("milestone_release_cardinality", pointer="/relations")
    relation = relations[0]
    index = next(index for index, item in enumerate(value["relations"]) if item is relation)
    target = relation.get("target")
    try:
        validate_builtin(target, _reference("REL"))
    except ModelError as error:
        raise ModelError("milestone_release_reference", pointer="/relations/" + str(index) + "/target") from error


def validate_domain_fields(value, *, expected_type=None):
    """Validate stored field values. This does not establish a verification result."""
    validate_common_fields(value, expected_type=expected_type)
    kind = value["artifact_type"]
    try:
        validate_builtin(value, domain_schema(kind, value["schema_version"]))
        if kind == "milestone":
            _milestone_release(value)
    except RecursionError as error:
        raise ModelError("unsupported_json_nesting") from error
