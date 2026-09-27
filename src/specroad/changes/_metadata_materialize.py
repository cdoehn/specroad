"""Materialize one candidate per identity after a selected pure policy.

This layer does not execute operations or decide lifecycle/authorization. The
per-artifact strategy supplies audit fields only for actual final changes.
"""
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ._common import _artifact
from ._patch_values import _snapshot
from ._metadata_policy import select_policy
from .metadata_values import MetadataArtifact, MetadataError, MetadataResult


def apply_policy(base, folded, binding):
    strategy = select_policy(binding["metadata_policy_version"])
    state = {value["id"]: value for value in folded.artifacts}
    candidates = []
    for item in folded.candidates:
        value = item.data
        if not item.changed:
            disposition = "unchanged"
        else:
            disposition, fields = strategy.fields(base.get(item.id), value, binding, item.id)
            value = {**value, **fields}
            try:
                _artifact(value, "/artifacts/" + item.id)
                canonical_json_sha256(value)  # Reject silent binary64 revision loss.
            except ModelError as error:
                raise MetadataError(error.reason, pointer=error.pointer) from None
        state[item.id] = value
        candidates.append(MetadataArtifact(
            item.id, _snapshot(value), item.base_sha256, canonical_json_sha256(value),
            item.operation_indices, disposition,
        ))
    ordered = [state[key] for key in sorted(state)]
    original = [base[key] for key in sorted(base)]
    return MetadataResult(
        _snapshot(ordered), tuple(candidates), _snapshot(binding),
        canonical_json_sha256(binding), canonical_json_sha256(original),
        canonical_json_sha256(ordered), folded.operations_applied, folded.preconditions_checked,
    )
