"""Guarded artifact update candidates, without live storage or publication."""
from __future__ import annotations
from dataclasses import dataclass, replace
from ..srx._json_values import JsonSnapshot
from ..storage.json_syntax import parse_json_object
from ..model.canonical import canonical_json_sha256
from .errors import ChangePlanError
from .values import ChangeOperation
from ._common import _artifact, _generic, _at
from ._patch_policy import _mutable_pointer
from ._patch_values import JsonPatchError, _snapshot
from .json_patch import apply_json_patch
from .field_patches import compile_field_patch


@dataclass(frozen=True)
class UpdatePreview:
    """Candidate field values, without revision advancement or publication."""
    operation: ChangeOperation
    _candidate: JsonSnapshot
    base_sha256: str
    candidate_sha256: str
    source_bytes: bytes | None = None
    operation_bytes: bytes | None = None

    @property
    def candidate(self):
        return self._candidate.data

    @property
    def changed(self):
        return self.base_sha256 != self.candidate_sha256

    @property
    def metadata_applied(self):
        return False

    @property
    def write_authorized(self):
        return False

    @property
    def validation_scope(self):
        return "update_candidate_only"


def preview_update(artifact, operation):
    """Check target/preconditions and protected fields, then isolate one update.

    Expected revision OR canonical artifact hash is mandatory; when both are
    present both must match. No current revision/time/user is invented. Checking
    supplied values is not an atomic live-storage check or proposal authorization.
    """
    current = _snapshot(artifact, "/artifact").data
    identity = _artifact(current, "/artifact")
    _generic(identity, "/artifact")
    op = operation if type(operation) is ChangeOperation else ChangeOperation(operation)
    value = op.data
    if value["op"] != "update":
        raise ChangePlanError("update_operation_required", pointer="/op")
    if value["target"] != identity.id:
        raise ChangePlanError("update_target_mismatch", pointer="/target", code="SRV146")
    before = _at("/artifact", canonical_json_sha256, current)
    if "expected_revision" in value and value["expected_revision"] != current["revision"]:
        raise ChangePlanError("expected_revision_mismatch", pointer="/expected_revision", code="SRV146")
    if "expected_sha256" in value and value["expected_sha256"] != before:
        raise ChangePlanError("expected_hash_mismatch", pointer="/expected_sha256", code="SRV146")
    # ChangeOperation already validates controlled destinations and move sources.
    result = apply_json_patch(current, value["patch"])
    candidate = result.data
    _artifact(candidate, "/candidate", expected_type=identity.artifact_type)
    after = _at("/candidate", canonical_json_sha256, candidate)
    return UpdatePreview(op, _snapshot(candidate), before, after)


def preview_update_bytes(artifact_bytes, operation_bytes):
    """Byte-preserving adapter. Expects an object update with explicit conditions."""
    for raw, pointer in ((artifact_bytes, "/artifact"), (operation_bytes, "/operation")):
        if type(raw) is not bytes:
            raise JsonPatchError("bytes_required", pointer=pointer)
    artifact = _at("/artifact", parse_json_object, artifact_bytes)
    operation = _at("/operation", parse_json_object, operation_bytes)
    result = preview_update(artifact, operation)
    return replace(result, source_bytes=artifact_bytes, operation_bytes=operation_bytes)


_UNSPECIFIED = object()


def preview_field_update(artifact, options, *, expected_revision=_UNSPECIFIED,
                         expected_sha256=_UNSPECIFIED):
    """Normalize authoring flags only after checking explicitly supplied guards.

    Passing None is not the same as omitting a guard. Neither revision nor hash
    is generated implicitly to turn a stale/unguarded edit into an accepted one.
    """
    base = _snapshot(artifact, "/artifact").data
    identity = _artifact(base, "/artifact")
    value = {"op": "update", "target": identity.id, "patch": []}
    if expected_revision is not _UNSPECIFIED:
        value["expected_revision"] = expected_revision
    if expected_sha256 is not _UNSPECIFIED:
        value["expected_sha256"] = expected_sha256
    preview_update(base, value)  # Check preconditions before parsing/editing.
    if type(options) not in (list, tuple):
        raise JsonPatchError("ordered_options_required", pointer="/options")
    for index, pair in enumerate(options):
        at = "/options/" + str(index)
        if type(pair) not in (list, tuple) or len(pair) != 2 or any(type(v) is not str for v in pair):
            raise JsonPatchError("option_pair_required", pointer=at)
        option, argument = pair
        if option == "--set":
            pointer, delimiter, _ = argument.partition("=")
            if not delimiter:
                raise JsonPatchError("set_assignment_required", pointer=at)
        elif option == "--unset":
            pointer = argument
        else:
            raise JsonPatchError("unknown_field_option", pointer=at)
        _mutable_pointer(pointer, at)
    value["patch"] = compile_field_patch(base, options).data
    return preview_update(base, value)
