"""Explicit, pure adapters for regular metadata and saved-plan verification.

No wall clock, filesystem, actor lookup, UUID generation, history adoption or
persistence is performed. Inputs must be stable while the caller provides them.
"""
from ..model.errors import ModelError
from ._common import _artifact
from ._fold_inputs import _inventory
from .folding import fold_operations
from ._metadata_policy import REGULAR_METADATA_POLICY, bind_policy
from ._metadata_materialize import apply_policy
from .metadata_values import MetadataError


def prepare_change_metadata(artifacts, operations, *, metadata_policy_version, actor,
                            planned_at, preconditions=(), source_files=None,
                            reserved_artifact_ids=(), reserved_relation_ids=()):
    """Fold regular operations, then stamp each changed identity exactly once.

    Repeating against the SAME base yields the SAME candidate. This does not
    make replay against an already modified live repository authorized. The
    existing operation preconditions continue to apply before metadata stamping.
    No-op and reverted changes retain ALL base values, including audit fields.
    """
    policy = bind_policy(metadata_policy_version, actor, planned_at)
    base, _, _ = _inventory(artifacts, reserved_artifact_ids)
    folded = fold_operations(list(base.values()), operations, preconditions=preconditions,
        source_files=source_files, reserved_artifact_ids=reserved_artifact_ids,
        reserved_relation_ids=reserved_relation_ids)
    return apply_policy(base, folded, policy)


def prepare_plan_metadata(plan, artifacts, *, observed_base_root, observed_scope,
                          source_files=None, reserved_artifact_ids=(),
                          reserved_relation_ids=()):
    """Recompute and verify the bound artifact results of a regular saved plan.

    The supplied root/scope observations are checked, not authenticated. The
    whole final project root and lifecycle remain for later planner stages.
    No wall-clock-dependent data is filled in during this verification.
    """
    from dataclasses import replace
    from .values import ChangePlan
    from .folding import fold_plan_fields
    if type(plan) is not ChangePlan:
        raise MetadataError("change_plan_required", pointer="/plan")
    value = plan.data
    policy = bind_policy(value["metadata_policy_version"], value["actor"], value["planned_at"])
    base, _, _ = _inventory(artifacts, reserved_artifact_ids)
    folded = fold_plan_fields(plan, list(base.values()), observed_base_root=observed_base_root,
        observed_scope=observed_scope, source_files=source_files,
        reserved_artifact_ids=reserved_artifact_ids, reserved_relation_ids=reserved_relation_ids)
    prepared = apply_policy(base, folded, policy)
    declared = {item["artifact"]["id"]: item for item in value["result_artifacts"]}
    if set(declared) != {item.id for item in prepared.candidates}:
        raise MetadataError("declared_result_set_mismatch", pointer="/result_artifacts")
    by_id = {item.id: item for item in prepared.candidates}
    for index, entry in enumerate(value["result_artifacts"]):
        actual = by_id[entry["artifact"]["id"]]
        if actual.candidate_sha256 != entry["sha256"]:
            raise MetadataError("declared_metadata_result_mismatch",
                                pointer="/result_artifacts/" + str(index))
    return replace(prepared, plan_sha256=plan.sha256, declared_artifacts_verified=True)


def prepare_change_metadata_bytes(sources, operations, *, metadata_policy_version,
                                  actor, planned_at, **fold_inputs):
    """Receive actual source bytes, without treating strings as file paths.

    Original bytes accompany touched results even when their representation is
    noncanonical. They are not a write target. An unchanged candidate retains
    exactly these original bytes, rather than stamping a new history revision.
    """
    from dataclasses import replace
    from ..storage.json_syntax import parse_json_object
    if type(sources) not in (list, tuple):
        raise MetadataError("byte_sequence_required", pointer="/sources")
    values, original = [], {}
    for index, raw in enumerate(sources):
        pointer = "/sources/" + str(index)
        if type(raw) is not bytes:
            raise MetadataError("bytes_required", pointer=pointer)
        try:
            value = parse_json_object(raw)
            identity = _artifact(value, pointer)
        except ModelError as error:
            raise MetadataError(error.reason, pointer=pointer) from None
        if identity.id in original:
            raise MetadataError("duplicate_artifact_id", pointer=pointer)
        original[identity.id] = raw
        values.append(value)
    prepared = prepare_change_metadata(values, operations, metadata_policy_version=metadata_policy_version,
        actor=actor, planned_at=planned_at, **fold_inputs)
    return replace(prepared, candidates=tuple(replace(item, original_bytes=original.get(item.id))
                                             for item in prepared.candidates))
