"""Closed regular Change Plan 1.2.0 and tagged operation contracts.

These are data contracts, not executable adapters or permission to publish.
Domain/lifecycle checks and live preconditions remain additional prerequisites.
"""
from ..model.artifact_schemas import DIALECT, MATURITIES
from ..model.audit_fields import audit_definitions

FORMAT_VERSION = "1.2.0"
METADATA_POLICY = "change-metadata-v1"
SCHEMA_ID = "urn:specroad:schema:1.2.0:change-plan"
OPERATION_TYPES = (
    "create", "update", "relation_add", "relation_remove", "transition", "retire",
    "evidence_record", "attachment_add", "attachment_remove", "representation_normalize",
    "relation_review_record", "proposal_control",
)


def obj(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties if required is None else required),
            "additionalProperties": False}


def arr(items):
    return {"type": "array", "items": items}


def text():
    return {"type": "string", "minLength": 1}


def digest():
    return {"type": "string", "pattern": r"^[0-9a-f]{64}(?![\s\S])"}


def revision():
    return {"type": "integer", "minimum": 1}


def expected(properties, required):
    result = obj({**properties, "expected_revision": revision(), "expected_sha256": digest()}, required)
    result["anyOf"] = [{"required": ["expected_revision"]}, {"required": ["expected_sha256"]}]
    return result


def patch_schema():
    # Shape only. RFC 6902 execution/array bounds belong to the next plan step.
    kinds = []
    for name in ("add", "remove", "replace", "move", "copy", "test"):
        fields = {"op": {"const": name}, "path": {"type": "string"}}
        if name in ("add", "replace", "test"):
            fields["value"] = True
        if name in ("move", "copy"):
            fields["from"] = {"type": "string"}
        # RFC 6902 permits additional members; they remain passive and hashed.
        branch = obj(fields); branch["additionalProperties"] = True; kinds.append(branch)
    return arr({"anyOf": kinds})


def operation_schema(kind):
    base = {"op": {"const": kind}}
    ref = text(); blob = {"type": "object"}
    if kind == "create":
        return obj({**base, "artifact": blob, "result_id": ref})
    if kind == "update":
        return expected({**base, "target": ref, "patch": patch_schema()}, ["op", "target", "patch"])
    if kind == "relation_add":
        return obj({**base, "source": ref, "relation": blob})
    if kind == "relation_remove":
        return obj({**base, "source": ref, "relation_id": ref,
                    "expected_sha256": digest(), "reason": text()})
    if kind == "transition":
        return obj({**base, "target": ref, "from": {"enum": list(MATURITIES)},
                    "to": {"enum": list(MATURITIES)}, "metadata": blob})
    if kind == "retire":
        return expected({**base, "target": ref, "reason": text()}, ["op", "target", "reason"])
    if kind == "evidence_record":
        return obj({**base, "evidence": blob})
    if kind == "attachment_add":
        return obj({**base, "target": ref, "attachment": obj({"path": text(), "media_type": text(),
                    "size": {"type": "integer", "minimum": 0}, "sha256": digest()})})
    if kind == "attachment_remove":
        return obj({**base, "target": ref, "path": text(), "expected_sha256": digest(), "reason": text()})
    if kind == "representation_normalize":
        return obj({**base, "path": text(), "expected_byte_sha256": digest(), "target_byte_sha256": digest()})
    if kind == "relation_review_record":
        withdrawal = expected({"target": ref, "reason": text()}, ["target", "reason"])
        return obj({**base, "record": blob, "source": ref, "target": ref, "approval_withdrawals": arr(withdrawal)})
    if kind == "proposal_control":
        event = obj({"from": text(), "to": text(), "reason": text(), "result_sha256": digest()})
        return obj({**base, "target": ref, "expected_revision": revision(), "expected_sha256": digest(),
                    "content_revision": revision(), "content_sha256": digest(),
                    "base_model_root_sha256": digest(), "change_plan_sha256": digest(),
                    "events": {"type": "array", "items": event, "minItems": 1}})
    raise ValueError("Unknown compiled operation kind")


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
        "change_plan_id": text(), "request_id": text(),
        "planned_at": defs["utc"], "actor": defs["actor"],
        "base": obj({"scope_descriptor": {"type": "object"}, "model_root_sha256": digest()}),
        "operations": arr({"anyOf": [operation_schema(kind) for kind in OPERATION_TYPES]}),
        "preconditions": arr(precondition_schema()),
        "result_artifacts": arr(obj({"artifact": {"type": "object"}, "sha256": digest()})),
        "expected_result": obj({"model_root_sha256": digest()}),
        "change_plan_sha256": digest(),
    }
    return {**obj(fields), "$defs": defs, "$schema": DIALECT, "$id": SCHEMA_ID,
            "x-specroad-validation-scope": "change_plan_fields_only",
            "description": "Regular typed Change Plan. No execution, state validation or write authorization."}
