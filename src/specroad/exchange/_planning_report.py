"""Bind candidate observations to the complete ordinary target assessment."""
from hashlib import sha256

from ..model.canonical import canonical_json_sha256


def _import_plan_report(changes, target, candidates, resource, *,
                        input_format, input_bytes, strategy, change_plan_id):
    operations, objects = changes.operations, changes.objects
    losses, diagnostics, conflicts = changes.losses, changes.diagnostics, changes.conflicts
    assessment = target.data
    plan = target.plan
    diagnostics.extend(assessment["validation"]["diagnostics"])
    created = [op["result_id"] for op in operations if op["op"] == "create"]
    updated = [op["target"] for op in operations if op["op"] == "update"]
    binding = {"input_format": input_format, "input_sha256": sha256(input_bytes).hexdigest(),
        "input_size": len(input_bytes), "mapping": resource.binding(),
        "mapping_source_sha256": resource.source_sha256,
        "candidates_sha256": canonical_json_sha256(candidates),
        "base_model_root_sha256": plan.data["base"]["model_root_sha256"],
        "change_plan_sha256": plan.sha256, "target_binding": assessment["binding"]}
    valid = target.target_validated and not losses and not conflicts and not any(
        item.get("exit_code", 0) for item in diagnostics)
    return {"format_version": "artifact-import-plan-v1", "binding": binding,
        "strategy": strategy, "change_plan_id": change_plan_id,
        "input_sha256": binding["input_sha256"], "mapping_sha256": resource.sha256,
        "operations": operations, "created_ids": sorted(created), "updated_ids": sorted(updated),
        "objects": objects, "skipped": [item for item in objects if item["action"] == "skip"],
        "conflicts": conflicts, "losses": losses, "diagnostics": diagnostics,
        "attachments": assessment["target_manifest"]["attachments"],
        "attachment_scope": "complete_supplied_target",
        "target_model_root_sha256": plan.data["expected_result"]["model_root_sha256"],
        "target_assessment": assessment, "change_plan": plan.data,
        "plan_valid": bool(valid), "exit_code": 0 if valid else max(3, assessment["validation"]["exit_code"]),
        "candidate_origin": "explicit_parsed_artifacts", "input_parsed": False,
        "import_completed": False, "execution_ready": False, "write_authorized": False}
