"""Regular Annex-K.2 metadata after ordered folding, with explicit bindings.

The caller owns a stable input snapshot. No wall clock, filesystem, actor
lookup, UUID generation, merge, migration or persistence is performed here.
"""
from ..model.audit import actor as read_actor
from ..model.audit_values import UtcTimestamp, Revision
from ..model.audit_fields import AUDIT_FIELDS
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ..model.identity_values import artifact_identity
from ._common import _artifact, _generic
from ._fold_inputs import _inventory
from ._patch_values import _snapshot
from .folding import fold_operations
from .metadata_time import next_update_time
from .metadata_values import MetadataArtifact, MetadataError, MetadataResult


REGULAR_METADATA_POLICY = "change-metadata-v1"


def _policy(version, actor, planned_at):
    if type(version) is not str or version != REGULAR_METADATA_POLICY:
        raise MetadataError("unsupported_regular_metadata_policy", pointer="/metadata_policy_version")
    try:
        bound_actor = read_actor(actor).as_fields()
        UtcTimestamp(planned_at)
    except ModelError as error:
        raise MetadataError(error.reason, pointer=error.pointer) from None
    return {"metadata_policy_version": version, "actor": bound_actor, "planned_at": planned_at}


def _apply_regular(base, folded, policy):
    state = {value["id"]: value for value in folded.artifacts}
    candidates = []
    for item in folded.candidates:
        value = item.data
        old = base.get(item.id)
        if not item.changed:
            disposition = "unchanged"
        else:
            # These are regular authoring candidates, not specialized immutable
            # record updates, proposal control, merge adoption or migration.
            try:
                _generic(artifact_identity(value), "/artifacts/" + item.id)
            except ModelError as error:
                raise MetadataError(error.reason, pointer=error.pointer) from None
            if old is None:
                disposition = "created"
                fields = {"revision": 1, "created_at": policy["planned_at"],
                          "updated_at": policy["planned_at"],
                          "created_by": policy["actor"], "updated_by": policy["actor"]}
            else:
                disposition = "changed"
                # Folding is explicitly pre-metadata. No operation may have
                # inserted its own intermediate audit update.
                if any(value[name] != old[name] for name in AUDIT_FIELDS):
                    raise MetadataError("intermediate_audit_changed", pointer="/artifacts/" + item.id)
                fields = {"revision": Revision(old["revision"]).value + 1,
                          "created_at": old["created_at"], "created_by": old["created_by"],
                          "updated_at": next_update_time(policy["planned_at"], old["updated_at"]),
                          "updated_by": policy["actor"]}
            value = {**value, **fields}
            try:
                _artifact(value, "/artifacts/" + item.id)
                canonical_json_sha256(value)  # No silent binary64 revision rounding.
            except ModelError as error:
                raise MetadataError(error.reason, pointer=error.pointer) from None
        state[item.id] = value
        candidates.append(MetadataArtifact(item.id, _snapshot(value), item.base_sha256,
            canonical_json_sha256(value), item.operation_indices, disposition))
    ordered = [state[key] for key in sorted(state)]
    original = [base[key] for key in sorted(base)]
    return MetadataResult(_snapshot(ordered), tuple(candidates), _snapshot(policy),
        canonical_json_sha256(policy), canonical_json_sha256(original),
        canonical_json_sha256(ordered), folded.operations_applied, folded.preconditions_checked)


def prepare_change_metadata(artifacts, operations, *, metadata_policy_version, actor,
                            planned_at, preconditions=(), source_files=None,
                            reserved_artifact_ids=(), reserved_relation_ids=()):
    """Fold regular operations, then stamp each changed identity exactly once.

    Repeating against the SAME base yields the SAME candidate. This does not
    make replay against an already modified live repository authorized. The
    existing operation preconditions continue to apply before metadata stamping.
    No-op and reverted changes retain ALL base values, including audit fields.
    """
    policy = _policy(metadata_policy_version, actor, planned_at)
    base, _, _ = _inventory(artifacts, reserved_artifact_ids)
    folded = fold_operations(list(base.values()), operations, preconditions=preconditions,
        source_files=source_files, reserved_artifact_ids=reserved_artifact_ids,
        reserved_relation_ids=reserved_relation_ids)
    return _apply_regular(base, folded, policy)


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
    policy = _policy(value["metadata_policy_version"], value["actor"], value["planned_at"])
    base, _, _ = _inventory(artifacts, reserved_artifact_ids)
    folded = fold_plan_fields(plan, list(base.values()), observed_base_root=observed_base_root,
        observed_scope=observed_scope, source_files=source_files,
        reserved_artifact_ids=reserved_artifact_ids, reserved_relation_ids=reserved_relation_ids)
    prepared = _apply_regular(base, folded, policy)
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
