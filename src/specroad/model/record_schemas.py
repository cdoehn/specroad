"""Passive field contracts for documents, references and workflow records.

This layer validates locally stored values, not graph completeness, trust,
external payload hashes, SRX semantics or permission to publish a record.
Loading an approved/recorded value never means that its provenance is verified.
"""

from ._schema import validate_builtin
from .artifact_schemas import artifact_common_schema, validate_common_fields
from .artifact_types import artifact_types
from .domain_fields import reference_schema
from .errors import ModelError
from .paths import project_path
from .versions import SCHEMA_VERSION

RECORD_TYPES = (
    "source", "verification", "test", "evidence", "baseline", "proposal", "issue",
    "document", "section", "content_block", "view", "code_ref", "relation_review", "configuration",
)
VALIDATION_SCOPE = "record_fields_only"
SPECIAL_STATES = {
    "evidence": ("evidence_state", {"recorded": "approved"}),
    "baseline": ("baseline_state", {"sealed": "approved"}),
    "relation_review": ("review_state", {"recorded": "approved"}),
    "proposal": ("proposal_status", {
        "draft": "draft", "validated": "proposed", "checked": "proposed",
        "in_review": "in_review", "approved": "approved", "applied": "approved",
        "rejected": "rejected", "stale": "retired",
    }),
}
VERIFICATION_METHODS = (
    "inspection", "review", "analysis", "simulation", "automated_test", "manual_test",
    "formal_proof", "monitoring", "audit", "measurement",
)
EVIDENCE_ORIGINS = ("recorded_manual", "imported_junit", "imported_sarif", "imported_generic", "generated_internal")
CODE_REFERENCE_KINDS = ("file", "line_range", "text_anchor", "symbol_hint", "generated_artifact")
BLOCK_KINDS = ("prose", "artifact_ref", "query", "table", "admonition", "page_break", "include_document")


def _object(properties, required=None):
    return {"type": "object", "required": list(properties if required is None else required),
            "properties": properties, "additionalProperties": False}


def _array(items, *, nonempty=False):
    return {"type": "array", "items": items, "minItems": int(nonempty)}


def _nullable(schema):
    return {"anyOf": [{"type": "null"}, schema]}


def _definitions():
    text = {"$ref": "#/$defs/text"}
    hash_value = {"type": "string", "pattern": r"^[0-9a-f]{64}(?![\s\S])"}
    artifact = {"anyOf": [reference_schema(t.prefix) for t in artifact_types()]}
    test = _nullable(reference_schema("TEST"))
    check = {"type": "string", "pattern": r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}(?![\s\S])"}
    scalar = {"anyOf": [{"type": t} for t in ("string", "number", "boolean", "null")]}
    return {
        "hash": hash_value, "artifact_ref": artifact, "check_id": check,
        "test_ref": test, "scalar": scalar,
        "attachment": _object({"path": text, "media_type": text,
                               "size": {"type": "integer", "minimum": 0}, "sha256": hash_value}),
        "evidence_subject": _object({"artifact_id": artifact, "revision": {"type": "integer", "minimum": 1},
                                     "artifact_sha256": hash_value, "verification_context_sha256": hash_value}),
        "run_context": _nullable(_object({"subject_id": text, "subject_state_sha256": hash_value,
                                           "run_id": text, "check_id": check, "test_id": test})),
        "evidence_slot": _object({"check_id": check, "test_id": test, "dimension": text}),
        "dimension": _object({"name": text, "allowed_values": _array(scalar, nonempty=True), "default": scalar},
                             ("name", "allowed_values")),
        "test_identity": {"anyOf": [_object({"external_id": text}), _object({"path": text})]},
        "producer": _object({"producer_type": {"enum": ["human", "tool", "ci", "monitoring", "ai"]}, "producer_id": text}),
        "tool": _object({"name": text, "version": text}),
    }


def _block_payload():
    text = {"$ref": "#/$defs/text"}
    # The payload remains passive. Parsing/rendering prose and queries belongs
    # to the document services, not a schema's successful read operation.
    prose = {"type": "string"}
    columns = _array({"type": "object"}, nonempty=True)
    view_source = _object({"source": {"const": "view"}})
    return {
        "prose": _object({"markdown": prose}),
        "artifact_ref": _object({"render_mode": {"enum": ["summary", "full", "link"]}}),
        "query": {"anyOf": [
            _object({"query": {"type": "object"}, "columns": columns, "empty_policy": {"enum": ["omit", "message", "error"]}}),
            _object({"source": {"const": "view"}, "columns": columns, "empty_policy": {"enum": ["omit", "message", "error"]}}),
        ]},
        "table": {"anyOf": [view_source, _object({"columns": columns, "rows": _array({"type": "array"})})]},
        "admonition": _object({"level": {"enum": ["note", "tip", "important", "warning", "caution"]},
                               "title": text, "markdown": prose}, ("level", "markdown")),
        "page_break": _object({}),
        "include_document": _object({"mode": {"enum": ["content", "section"]}}),
    }


def _type_fields(kind):
    text = {"$ref": "#/$defs/text"}
    utc = {"$ref": "#/$defs/utc"}
    sha = {"$ref": "#/$defs/hash"}
    obj = {"type": "object"}
    refs = _array({"$ref": "#/$defs/artifact_ref"}, nonempty=True)
    texts = _array(text)
    detail = {"anyOf": [text, {"type": "object", "not": {"const": {}}}]}
    specifications = {
        "source": (("source_kind", "locator", "captured_at"),
                   {"source_kind": text, "locator": text, "captured_at": utc, "content_sha256": sha, "excerpt": text}),
        "verification": (("method", "subjects", "preconditions", "procedure", "oracle", "evidence_kinds", "evidence_slots", "dimensions", "configuration_policy"),
                         {"method": {"enum": list(VERIFICATION_METHODS)}, "subjects": refs,
                          "preconditions": texts, "procedure": {"anyOf": [text, _array(text, nonempty=True)]},
                          "oracle": detail, "evidence_kinds": _array(text, nonempty=True),
                          "evidence_slots": _array({"$ref": "#/$defs/evidence_slot"}, nonempty=True),
                          "dimensions": _array(text, nonempty=True), "configuration_policy": {"enum": ["independent", "bound"]}}),
        "test": (("test_identity", "test_type", "oracle"),
                 {"test_identity": {"$ref": "#/$defs/test_identity"}, "test_type": text, "oracle": detail}),
        "evidence": (("result", "produced_at", "producer", "tool", "environment", "subjects", "origin", "run_context"),
                     {"result": text, "produced_at": utc, "producer": {"$ref": "#/$defs/producer"},
                      "tool": {"$ref": "#/$defs/tool"}, "environment": obj,
                      "subjects": _array({"$ref": "#/$defs/evidence_subject"}, nonempty=True),
                      "origin": {"enum": list(EVIDENCE_ORIGINS)}, "run_context": {"$ref": "#/$defs/run_context"},
                      "unbound_reason": text, "configuration_hash": _nullable(sha),
                      "configuration_policy": {"enum": ["independent", "bound"]},
                      "attachments": _array({"$ref": "#/$defs/attachment"})}),
        "baseline": (("baseline_kind", "scope_descriptor", "manifest", "model_root_sha256"),
                     {"baseline_kind": {"enum": ["working", "release"]}, "scope_descriptor": obj,
                      "manifest": _array(obj), "model_root_sha256": sha, "configuration_hash": _nullable(sha),
                      "profiles": _array(obj), "tool_version": text, "verification_evaluation": obj}),
        "proposal": (("content_revision", "content_sha256", "control_history", "base", "change_plan", "rationale"),
                     {"content_revision": {"type": "integer", "minimum": 1}, "content_sha256": sha,
                      "control_history": _array(obj), "base": obj, "change_plan": obj, "rationale": text, "reviews": _array(obj)}),
        "issue": (("description", "issue_status", "owner"),
                  {"description": text, "issue_status": text, "resolution_criteria": {"anyOf": [text, _array(text, nonempty=True)]},
                   "permanent_status_reason": text}),
        "document": (("purpose", "audience", "language", "document_role", "render_policy"),
                     {"purpose": text, "audience": {"anyOf": [text, _array(text, nonempty=True)]},
                      "document_role": {"enum": ["primary_specification", "supporting"]}, "render_policy": obj}),
        # A parent link is stored at its source. The single incoming contains
        # constraint cannot be established from one section's own JSON file.
        "section": ((), {}),
        "content_block": (("block_kind", "payload"), {"block_kind": {"enum": list(BLOCK_KINDS)}, "payload": obj}),
        "view": (("scope_descriptor", "filter", "columns", "sort", "grouping", "relation_projections", "formats"),
                 {"scope_descriptor": obj, "filter": obj, "columns": _array(obj, nonempty=True),
                  "sort": _array(obj), "grouping": _array(obj), "relation_projections": _array(obj),
                  "formats": _array(text, nonempty=True)}),
        "code_ref": (("path", "reference_kind", "file_sha256"),
                     {"path": text, "reference_kind": {"enum": list(CODE_REFERENCE_KINDS)}, "file_sha256": sha,
                      "git_commit": {"type": "string", "pattern": r"^(?:[0-9a-f]{40}|[0-9a-f]{64})(?![\s\S])"},
                      "git_blob": {"type": "string", "pattern": r"^(?:[0-9a-f]{40}|[0-9a-f]{64})(?![\s\S])"},
                      "start_line": {"type": "integer", "minimum": 1}, "end_line": {"type": "integer", "minimum": 1},
                      "encoding": text, "selection_sha256": sha, "anchor": obj, "symbol_hint": text}),
        "relation_review": (("relation_id", "relation_content_sha256", "source_context_sha256", "target_context_sha256", "reviewer", "decision"),
                            {"relation_id": {"type": "string", "pattern": r"^REL-[0-7][0-9A-HJKMNP-TV-Z]{25}(?![\s\S])"},
                             "relation_content_sha256": sha, "source_context_sha256": sha, "target_context_sha256": sha,
                             "context_hash_algorithm": {"const": "relation_context_hash-v1"},
                             "reviewer": _object({"actor_type": {"const": "human"}, "actor_id": text}),
                             "decision": {"enum": ["confirmed", "rejected"]}, "reason": text}),
        "configuration": (("name", "dimensions", "selection"),
                          {"name": text, "dimensions": _array({"$ref": "#/$defs/dimension"}),
                           "selection": {"type": "object", "additionalProperties": {"$ref": "#/$defs/scalar"}},
                           "parent": _nullable(reference_schema("CFG"))}),
    }
    return specifications[kind]


def record_schema(kind, version=SCHEMA_VERSION):
    """Return a detached schema. It is not a workflow command or a write permit."""
    schema = artifact_common_schema(kind, version)
    if kind not in RECORD_TYPES:
        raise ModelError("record_type_not_supported", pointer="/artifact_type")
    required, fields = _type_fields(kind)
    schema["$id"] = "urn:specroad:schema:" + version + ":artifact-record:" + kind
    schema["$comment"] = "Local record fields only; no graph, payload integrity, review or publication approval."
    schema["x-specroad-validation-scope"] = VALIDATION_SCOPE
    schema["$defs"].update(_definitions())
    schema["required"] = list(dict.fromkeys([*schema["required"], *required]))
    schema["properties"].update(fields)
    schema["additionalProperties"] = False
    conditions = []
    if kind in SPECIAL_STATES:
        field, states = SPECIAL_STATES[kind]
        schema["required"].append(field)
        schema["properties"][field] = {"enum": list(states)}
        conditions.append({"anyOf": [{"properties": {field: {"const": state}, "maturity": {"const": maturity}}}
                                      for state, maturity in states.items()]})
    if kind == "content_block":
        conditions.append({"anyOf": [{"properties": {"block_kind": {"const": block}, "payload": payload}}
                                      for block, payload in _block_payload().items()]})
    if kind == "configuration":
        schema["properties"].pop("applicability", None)
    if kind == "source":
        conditions.append({"anyOf": [{"properties": {"maturity": {"not": {"const": "approved"}}}},
                                      {"required": ["content_sha256"]}, {"required": ["excerpt"]}]})
    if kind == "evidence":
        conditions.append({"anyOf": [{"properties": {"run_context": {"not": {"type": "null"}}}},
                                      {"required": ["unbound_reason"]}]})
    schema["allOf"] = conditions
    return schema


def _safe_path(value, pointer):
    try:
        project_path(value)
    except ModelError as error:
        raise ModelError(error.reason, pointer=pointer) from error


def validate_record_fields(value, *, expected_type=None):
    """Validate field values without loading any referenced file or service."""
    validate_common_fields(value, expected_type=expected_type)
    kind = value["artifact_type"]
    try:
        validate_builtin(value, record_schema(kind, value["schema_version"]))
        if kind == "code_ref":
            _safe_path(value["path"], "/path")
        if kind == "test" and "path" in value["test_identity"]:
            _safe_path(value["test_identity"]["path"], "/test_identity/path")
        if kind == "evidence":
            for index, attachment in enumerate(value.get("attachments", ())):
                _safe_path(attachment["path"], "/attachments/" + str(index) + "/path")
    except RecursionError as error:
        raise ModelError("unsupported_json_nesting") from error


def require_generic_mutation(kind, operation):
    """A routing PRECONDITION for future services, never publication authorization.

Specialized records require their dedicated commands even if their bytes pass
schema validation. No generic create, free patch or lifecycle transition may
manufacture an Evidence, Baseline, Proposal or Relationsreview.
"""
    if kind not in RECORD_TYPES:
        raise ModelError("record_type_not_supported", pointer="/artifact_type")
    if operation not in ("create", "patch", "lifecycle"):
        raise ModelError("unknown_mutation_operation")
    if kind in SPECIAL_STATES:
        raise ModelError("specialized_operation_required", pointer="/artifact_type")
