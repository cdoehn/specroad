"""Envelope and local cross-record bindings, independent of operation storage."""
from ..model._schema import validate_builtin
from ..model.canonical import canonical_json_sha256
from ..model.audit_values import Actor, UtcTimestamp
from ..model.paths import project_path
from ..graph.scope_descriptors import ScopeDescriptor
from ._common import _at, _text, _reference, _artifact
from .operation_registry import validate_operation as _validate_operation, result_owners as _targets
from .schema import METADATA_POLICY, change_plan_schema
from .errors import ChangePlanError

def _result_bindings(value):
    """Check local declarations only; never resolve project paths or revisions."""
    results = {v["artifact"]["id"]: v for v in value["result_artifacts"]}
    owners, created, relations = set(), set(), set()
    counts = {}
    for op in value["operations"]:
        for target in _targets(op):
            counts[target] = counts.get(target, 0) + 1
    for index, operation in enumerate(value["operations"]):
        at = "/operations/" + str(index)
        owners.update(_targets(operation))
        kind = operation["op"]
        if kind in ("create", "evidence_record", "relation_review_record"):
            field = {"create": "artifact", "evidence_record": "evidence", "relation_review_record": "record"}[kind]
            artifact = operation[field]
            if artifact["id"] in created:
                raise ChangePlanError("duplicate_creation_identity", pointer=at, code="SRV146")
            created.add(artifact["id"])
            if artifact["id_scheme"] != "random128-v1":
                raise ChangePlanError("new_identity_requires_random128", pointer=at + "/" + field + "/id_scheme")
            if (kind != "create" or counts[artifact["id"]] == 1) and artifact["id"] in results:
                if canonical_json_sha256(artifact) != results[artifact["id"]]["sha256"]:
                    raise ChangePlanError("immutable_record_result_mismatch" if kind != "create" else "creation_result_mismatch", pointer=at, code="SRV146")
        if kind == "proposal_control" and operation["target"] in results:
            final = results[operation["target"]]["artifact"]
            if (final["content_revision"] != operation["content_revision"]
                    or final["content_sha256"] != operation["content_sha256"]
                    or final["proposal_status"] != operation["events"][-1]["to"]):
                raise ChangePlanError("proposal_control_result_mismatch", pointer=at, code="SRV146")
        if kind == "relation_add":
            identity = operation["relation"]["relation_id"]
            if identity in relations:
                raise ChangePlanError("duplicate_new_relation_id", pointer=at + "/relation/relation_id")
            relations.add(identity)
        if kind == "relation_review_record" and value["actor"]["actor_type"] != "human":
            raise ChangePlanError("human_review_planner_required", pointer="/actor")
    if set(results) != owners:
        raise ChangePlanError("result_owner_set_mismatch", pointer="/result_artifacts", code="SRV146")
    if not value["operations"] and value["base"]["model_root_sha256"] != value["expected_result"]["model_root_sha256"]:
        raise ChangePlanError("empty_plan_changed_root", pointer="/expected_result", code="SRV146")
    # Duplicate assertions cannot hide contradictory conditions behind order.
    seen = set()
    for index, condition in enumerate(value["preconditions"]):
        key = (("artifact", condition["artifact_id"]) if condition["kind"] == "artifact"
               else ("path", condition["path"]))
        if key in seen:
            raise ChangePlanError("duplicate_precondition_target", pointer="/preconditions/" + str(index))
        seen.add(key)

def _validate_plan(value, *, hash_present=True):
    if type(value) is not dict:
        raise ChangePlanError("plan_object_required")
    if value.get("metadata_policy_version") != METADATA_POLICY:
        raise ChangePlanError("unsupported_regular_metadata_policy", pointer="/metadata_policy_version", code="SRV174")
    schema = change_plan_schema()
    # Dispatch tagged operation validation separately for precise diagnostics;
    # the public schema still exposes the complete union of payload contracts.
    schema["properties"]["operations"]["items"] = {"type": "object"}
    if not hash_present:
        schema["required"].remove("change_plan_sha256")
        schema["properties"].pop("change_plan_sha256")
    _at("", validate_builtin, value, schema)
    for name in ("change_plan_id", "request_id"):
        _text(value[name], "/" + name)
    _at("/planned_at", UtcTimestamp, value["planned_at"])
    _at("/actor", Actor, **value["actor"])
    _at("/base/scope_descriptor", ScopeDescriptor, value["base"]["scope_descriptor"])
    for index, operation in enumerate(value["operations"]):
        _validate_operation(operation, "/operations/" + str(index))
    for index, precondition in enumerate(value["preconditions"]):
        at = "/preconditions/" + str(index)
        if precondition["kind"] == "artifact":
            _reference(precondition["artifact_id"], at + "/artifact_id")
        else:
            _at(at + "/path", project_path, precondition["path"])
    seen = set()
    for index, result in enumerate(value["result_artifacts"]):
        at = "/result_artifacts/" + str(index)
        identity = _artifact(result["artifact"], at + "/artifact")
        if identity.id in seen:
            raise ChangePlanError("duplicate_result_identity", pointer=at, code="SRV146")
        seen.add(identity.id)
        if canonical_json_sha256(result["artifact"]) != result["sha256"]:
            raise ChangePlanError("result_hash_mismatch", pointer=at + "/sha256", code="SRV146")
    _result_bindings(value)
    if hash_present:
        expected = canonical_json_sha256({k: v for k, v in value.items() if k != "change_plan_sha256"})
        if expected != value["change_plan_sha256"]:
            raise ChangePlanError("change_plan_hash_mismatch", pointer="/change_plan_sha256", code="SRV146")

