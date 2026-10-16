"""Passive field contracts for documents, references and workflow records.

This layer validates locally stored values, not graph completeness, trust,
external payload hashes, SRX semantics or permission to publish a record.
Loading an approved/recorded value never means that its provenance is verified.
"""

import re

from .._metadata import SRX_LANGUAGE_VERSION
from ._schema import validate_builtin, _json_equal
from .artifact_schemas import artifact_common_schema, validate_common_fields
from .artifact_types import artifact_types
from .domain_fields import reference_schema
from .errors import ModelError
from .paths import project_path
from .versions import SCHEMA_VERSION
from .record_contracts import RECORD_TYPES, SPECIAL_STATES, VALIDATION_SCOPE, record_contract
from ._field_shapes import _object, _array, _typed_reference
from ._content_block_fields import BLOCK_KINDS, _block_payload, _block_reference

VERIFICATION_METHODS = (
    "inspection", "review", "analysis", "simulation", "automated_test", "manual_test",
    "formal_proof", "monitoring", "audit", "measurement",
)
EVIDENCE_ORIGINS = ("recorded_manual", "imported_junit", "imported_sarif", "imported_generic", "generated_internal")
CODE_REFERENCE_KINDS = ("file", "line_range", "text_anchor", "symbol_hint", "generated_artifact")


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
                      "document_role": {"enum": ["primary_specification", "supporting"]}, "render_policy": obj,
                      "language_policy_override": _object({"mixed_languages": {"enum": ["allow", "warning", "error"]}}, ())}),
        # A parent link is stored at its source. The single incoming contains
        # constraint cannot be established from one section's own JSON file.
        "section": ((), {"language_policy_override": _object({"mixed_languages": {"enum": ["allow", "warning", "error"]}}, ())}),
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
                             "source_id": {"$ref": "#/$defs/artifact_ref"},
                             "target_id": {"$ref": "#/$defs/artifact_ref"},
                             "source_revision": {"type": "integer", "minimum": 1},
                             "target_revision": {"type": "integer", "minimum": 1},
                             "source_artifact_sha256": sha, "target_artifact_sha256": sha,
                             "reviewed_at": {"$ref": "#/$defs/utc"}, "comment": text,
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
    contract = record_contract(kind)
    required, fields = _type_fields(kind)
    schema["$id"] = contract.schema_id
    schema["$comment"] = "Local record fields only; no graph, payload integrity, review or publication approval."
    schema["x-specroad-validation-scope"] = contract.validation_scope
    schema["description"] = "Stored record fields for " + kind + "; not evidence verification, lifecycle approval or graph validation."
    schema["$defs"].update(_definitions())
    schema["required"] = list(dict.fromkeys([*schema["required"], *required]))
    schema["properties"].update(fields)
    schema["additionalProperties"] = False
    conditions = []
    if contract.requires_specialized_operation:
        field = contract.status_field
        schema["required"].append(field)
        schema["properties"][field] = {"enum": [state for state, _ in contract.state_maturities]}
        conditions.append({"anyOf": [{"properties": {field: {"const": state}, "maturity": {"const": maturity}}}
                                      for state, maturity in contract.state_maturities]})
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
    if kind == "issue":
        conditions.append({"anyOf": [{"properties": {"maturity": {"not": {"const": "approved"}}}},
                                      {"required": ["resolution_criteria"]}, {"required": ["permanent_status_reason"]}]})
    if kind == "code_ref":
        for reference_kind, required in (
            ("line_range", ("start_line", "end_line", "encoding", "selection_sha256")),
            ("text_anchor", ("anchor", "selection_sha256")),
            ("symbol_hint", ("symbol_hint",)),
        ):
            conditions.append({"anyOf": [{"properties": {"reference_kind": {"not": {"const": reference_kind}}}},
                                          {"required": list(required)}]})
        schema["properties"]["anchor"] = {"type": "object", "not": {"const": {}}}
    if kind == "view":
        schema["properties"]["filter"] = _object({
            "language": {"const": "srx"}, "version": {"const": SRX_LANGUAGE_VERSION}, "expression": {"type": "object"},
        })
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
        _validate_local_record(value)
    except RecursionError as error:
        raise ModelError("unsupported_json_nesting") from error


def require_generic_mutation(kind, operation, *, field_paths=()):
    """A routing PRECONDITION for future services, never publication authorization.

Specialized records require their dedicated commands even if their bytes pass
schema validation. No generic create, free patch or lifecycle transition may
manufacture an Evidence, Baseline, Proposal or Relationsreview.
"""
    contract = record_contract(kind)
    if operation not in ("create", "patch", "lifecycle"):
        raise ModelError("unknown_mutation_operation")
    if contract.requires_specialized_operation:
        raise ModelError("specialized_operation_required", pointer="/artifact_type")
    if type(field_paths) not in (tuple, list):
        raise ModelError("field_path_sequence_required")
    for pointer in field_paths:
        if type(pointer) is not str or not pointer.startswith("/") or pointer == "/":
            raise ModelError("invalid_field_pointer")
        if re.search(r"~(?![01])", pointer):
            raise ModelError("invalid_field_pointer", pointer=pointer)
        top = pointer.split("/", 2)[1].replace("~1", "/").replace("~0", "~")
        if top in {"id", "id_scheme", "artifact_type", "schema_version", "maturity", "revision",
                   "created_at", "created_by", "updated_at", "updated_by"}:
            raise ModelError("controlled_field_mutation", pointer=pointer)


def _unique(values, *, reason, pointer):
    """JSON equality, not Python's equality of True and 1. No input sorting."""
    for index, value in enumerate(values):
        if any(_json_equal(value, previous) for previous in values[:index]):
            raise ModelError(reason, pointer=pointer + "/" + str(index))


def _local_contains(value):
    kind = value["artifact_type"]
    prefixes = ("SEC",) if kind == "document" else ("SEC", "BLOCK")
    for index, relation in enumerate(value["relations"]):
        if relation.get("type") != "contains":
            continue
        pointer = "/relations/" + str(index)
        position = relation.get("position")
        if type(position) is not int or position < 0:
            raise ModelError("invalid_contains_position", pointer=pointer + "/position")
        try:
            _typed_reference(relation.get("target"), prefixes)
        except ModelError as error:
            raise ModelError("invalid_contains_target", pointer=pointer + "/target") from error
    # Do not decide parent cardinality or cyclic inclusion without a graph.
    # Equal positions are legal and will use the specified ID tie-breaker.


def _configuration_fields(value):
    dimensions = value["dimensions"]
    _unique([dimension["name"] for dimension in dimensions], reason="duplicate_dimension", pointer="/dimensions")
    declared = {dimension["name"]: dimension for dimension in dimensions}
    parent = value.get("parent")
    if parent == value["id"]:
        raise ModelError("configuration_self_parent", pointer="/parent")
    for index, dimension in enumerate(dimensions):
        allowed = dimension["allowed_values"]
        _unique(allowed, reason="duplicate_allowed_value", pointer="/dimensions/" + str(index) + "/allowed_values")
        if "default" in dimension and not any(_json_equal(dimension["default"], choice) for choice in allowed):
            raise ModelError("invalid_dimension_default", pointer="/dimensions/" + str(index) + "/default")
        if parent is None and dimension["name"] not in value["selection"] and "default" not in dimension:
            raise ModelError("missing_dimension_selection", pointer="/selection")
    for name, selection in value["selection"].items():
        if not name.strip() or "\0" in name:
            raise ModelError("invalid_dimension_name", pointer="/selection")
        if name not in declared:
            if parent is None:
                raise ModelError("unknown_dimension", pointer="/selection")
            continue  # Inherited dimensions are resolved by the later graph service.
        if not any(_json_equal(selection, choice) for choice in declared[name]["allowed_values"]):
            raise ModelError("invalid_dimension_selection", pointer="/selection")


def _validate_local_record(value):
    """Only contradictions decidable from this one record; never resolve its graph."""
    kind = value["artifact_type"]
    if kind == "verification":
        _unique(value["subjects"], reason="duplicate_subject", pointer="/subjects")
        _unique(value["dimensions"], reason="duplicate_verification_dimension", pointer="/dimensions")
        _unique([slot["check_id"] for slot in value["evidence_slots"]], reason="duplicate_check_id", pointer="/evidence_slots")
        for index, slot in enumerate(value["evidence_slots"]):
            if slot["dimension"] not in value["dimensions"]:
                raise ModelError("unknown_check_dimension", pointer="/evidence_slots/" + str(index) + "/dimension")
    elif kind == "evidence":
        _unique([subject["artifact_id"] for subject in value["subjects"]], reason="duplicate_subject", pointer="/subjects")
        _unique([item["path"] for item in value.get("attachments", ())], reason="duplicate_attachment", pointer="/attachments")
        if value.get("configuration_policy") == "bound" and value.get("configuration_hash") is None:
            raise ModelError("missing_configuration_binding", pointer="/configuration_hash")
    elif kind == "proposal":
        if value["content_revision"] > value["revision"]:
            raise ModelError("content_revision_exceeds_revision", pointer="/content_revision")
    elif kind in ("document", "section"):
        _local_contains(value)
    elif kind == "content_block":
        _block_reference(value)
    elif kind == "code_ref":
        if value["reference_kind"] == "line_range" and value["end_line"] < value["start_line"]:
            raise ModelError("invalid_line_range", pointer="/end_line")
    elif kind == "configuration":
        _configuration_fields(value)
