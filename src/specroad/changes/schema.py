"""Closed, detached schema for regular Change Plans, format 1.2.0."""
from ..model.schema_identity import (DIALECT, CHANGE_PLAN_VERSION as FORMAT_VERSION,
                                     CHANGE_PLAN_ID as SCHEMA_ID, CHANGE_PLAN_SCOPE)
from ..model.audit_fields import audit_definitions
from ._schema_fields import obj, arr, text, digest, revision, expected
from .operation_registry import OPERATION_TYPES, operation_schema
from .request_ids import request_id_schema

METADATA_POLICY = "change-metadata-v1"

def precondition_schema():
    return {"anyOf": [
        expected({"kind": {"const": "artifact"}, "artifact_id": text()}, ["kind", "artifact_id"]),
        obj({"kind": {"const": "file"}, "path": text(), "expected_byte_sha256": digest()}),
        obj({"kind": {"const": "absent"}, "path": text()}),
    ]}

def change_plan_schema():
    """Return a detached schema; no global cache, file access or external refs."""
    defs = audit_definitions()
    fields = {
        "format_version": {"const": FORMAT_VERSION},
        "metadata_policy_version": {"const": METADATA_POLICY},
        "change_plan_id": text(), "request_id": request_id_schema(),
        "planned_at": defs["utc"], "actor": defs["actor"],
        "base": obj({"scope_descriptor": {"type": "object"}, "model_root_sha256": digest()}),
        "operations": arr({"anyOf": [operation_schema(kind) for kind in OPERATION_TYPES]}),
        "preconditions": arr(precondition_schema()),
        "result_artifacts": arr(obj({"artifact": {"type": "object"}, "sha256": digest()})),
        "expected_result": obj({"model_root_sha256": digest()}),
        "change_plan_sha256": digest(),
    }
    return {**obj(fields), "$defs": defs, "$schema": DIALECT, "$id": SCHEMA_ID,
            "x-specroad-validation-scope": CHANGE_PLAN_SCOPE,
            "description": "Regular typed Change Plan. No execution, state validation or write authorization."}
