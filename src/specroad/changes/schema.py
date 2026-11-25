"""Closed, detached schema for regular and migration Change Plans, format 1.2.0."""
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

def change_plan_schema(*, additive_migration=True, version=FORMAT_VERSION):
    """Return a detached schema; no global cache, file access or external refs."""
    def schema_for(kind):
        if kind == "schema_migrate":
            from ..migration.plan_contract import migration_operation_schema
            return migration_operation_schema(additive=additive_migration)
        return operation_schema(kind)
    defs = audit_definitions()
    fields = {
        "format_version": {"const": version},
        "metadata_policy_version": {"enum": [METADATA_POLICY, "migration-metadata-v1", "merge-metadata-v1"]},
        "change_plan_id": text(), "request_id": request_id_schema(),
        "planned_at": defs["utc"], "actor": defs["actor"],
        "base": obj({"scope_descriptor": {"type": "object"}, "model_root_sha256": digest()}),
        "operations": arr({"anyOf": [schema_for(kind) for kind in (*OPERATION_TYPES, "schema_migrate", "merge_publish")]}),
        "preconditions": arr(precondition_schema()),
        "result_artifacts": arr(obj({"artifact": {"type": "object"}, "sha256": digest()})),
        "expected_result": obj({"model_root_sha256": digest()}),
        "change_plan_sha256": digest(),
    }
    if version in ('1.3.0', '1.4.0'):
        fields['force'] = obj({'requested': {'type': 'boolean'},
            'reason': {'anyOf': [text(), {'type': 'null'}]}})
        fields['project_id'] = text()
        for section in ('base', 'expected_result'):
            fields[section]['properties']['model_root_sha256'] = {'anyOf': [digest(), {'type': 'null'}]}
    elif version != FORMAT_VERSION:
        raise ValueError('Unsupported ChangePlan version')
    if version == '1.4.0':
        fields['native_intent'] = obj({'command_id': text(), 'intent': {'type': 'object'},
            'expected_model_root_sha256': {'anyOf': [digest(), {'type': 'null'}]},
            'as_proposal': {'type': 'boolean'},
            'proposal_fields': {'anyOf': [{'type': 'object'}, {'type': 'null'}]},
            'execution_binding': {'anyOf': [{'type': 'null'}, obj({
                'planned_at': defs['utc'], 'change_plan_id': text(), 'transaction_id': text()})]}})
    result = obj(fields)
    result["anyOf"] = [
        {"properties": {"metadata_policy_version": {"const": METADATA_POLICY},
            "operations": {"items": {"not": {"properties": {"op": {"enum": ["schema_migrate", "merge_publish"]}}, "required": ["op"]}}}}},
        {"properties": {"metadata_policy_version": {"const": "migration-metadata-v1"},
            "operations": {"minItems": 1, "not": {"minItems": 2},
                "items": schema_for("schema_migrate")}}},
        {"properties": {"metadata_policy_version": {"const": "merge-metadata-v1"},
            "operations": {"minItems": 1, "not": {"minItems": 2},
                "items": operation_schema("merge_publish")}}},
    ]
    return {**result, "$defs": defs, "$schema": DIALECT, "$id": "urn:specroad:schema:" + version + ":change-plan",
            "x-specroad-validation-scope": CHANGE_PLAN_SCOPE,
            "description": "Typed Change Plan. No execution, state validation or write authorization."}
