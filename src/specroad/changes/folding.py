"""Ordered in-memory field evaluation; no metadata advancement or publication.

The caller must keep input containers stable while their private copies are made.
Specialized lifecycle/evidence/attachment/control operations are refused until
implemented by their own planner steps, never treated as successful no-ops.
"""
from dataclasses import replace
import re
from ..model.canonical import canonical_json_sha256
from ..model._schema import validate_builtin
from ..model.errors import ModelError
from ..model.paths import project_path
from ..graph.scope_descriptors import ScopeDescriptor
from ._common import _artifact, _generic, _reference, _at
from ._patch_values import _snapshot
from .schema import precondition_schema
from .values import ChangePlan, ChangeOperation
from .update_preview import preview_update
from .folding_values import FoldError, FoldedArtifact, OperationFold

SUPPORTED_FOLD_OPERATIONS = ("create", "update")


def _owned_sequence(value, pointer):
    if type(value) not in (list, tuple):
        raise FoldError("ordered_sequence_required", pointer=pointer)
    return _snapshot(list(value), pointer).data


def _inventory(artifacts, reserved_artifact_ids):
    owned = _owned_sequence(artifacts, "/artifacts")
    state, prefixes = {}, set()
    for index, artifact in enumerate(owned):
        identity = _artifact(artifact, "/artifacts/" + str(index))
        if identity.id in state:
            raise FoldError("duplicate_artifact_id", pointer="/artifacts/" + str(index) + "/id")
        state[identity.id] = artifact
        prefixes.add(identity.id_prefix)
    if len(prefixes) > 1:
        raise FoldError("mixed_project_prefix", pointer="/artifacts")
    reserved = _owned_sequence(reserved_artifact_ids, "/reserved_artifact_ids")
    seen = set(state)
    for index, token in enumerate(reserved):
        identity = _reference(token, "/reserved_artifact_ids/" + str(index))
        prefixes.add(identity.id_prefix)
        seen.add(identity.id)
    if len(prefixes) > 1:
        raise FoldError("mixed_project_prefix", pointer="/reserved_artifact_ids")
    return state, seen, prefixes


def _files(source_files):
    if source_files is None:
        return None
    if type(source_files) is not dict:
        raise FoldError("file_snapshot_mapping_required", pointer="/source_files")
    result = {}
    for path, raw in source_files.items():
        _at("/source_files", project_path, path)
        if type(raw) is not bytes:
            raise FoldError("file_bytes_required", pointer="/source_files")
        result[path] = raw
    return result


def _check_expected(artifact, value):
    if "expected_revision" in value and value["expected_revision"] != artifact["revision"]:
        raise FoldError("expected_revision_mismatch", pointer="/expected_revision", code="SRV146")
    if "expected_sha256" in value and value["expected_sha256"] != canonical_json_sha256(artifact):
        raise FoldError("expected_hash_mismatch", pointer="/expected_sha256", code="SRV146")


def _preflight(state, conditions, source_files):
    from hashlib import sha256
    values = _owned_sequence(conditions, "/preconditions")
    seen = set()
    for index, value in enumerate(values):
        pointer = "/preconditions/" + str(index)
        try:
            _at("", validate_builtin, value, precondition_schema())
            kind = value["kind"]
            key = ("artifact", value["artifact_id"]) if kind == "artifact" else ("path", value["path"])
            if key in seen:
                raise FoldError("duplicate_precondition_target")
            seen.add(key)
            if kind == "artifact":
                _reference(value["artifact_id"], "/artifact_id")
                if value["artifact_id"] not in state:
                    raise FoldError("missing_precondition_artifact", pointer="/artifact_id", code="SRV146")
                _check_expected(state[value["artifact_id"]], value)
            else:
                _at("/path", project_path, value["path"])
                if source_files is None:
                    raise FoldError("file_snapshot_required", pointer="/path")
                if kind == "absent":
                    if value["path"] in source_files:
                        raise FoldError("expected_absence_mismatch", pointer="/path", code="SRV146")
                elif value["path"] not in source_files or sha256(source_files[value["path"]]).hexdigest() != value["expected_byte_sha256"]:
                    raise FoldError("expected_file_hash_mismatch", pointer="/path", code="SRV146")
        except ModelError as error:
            raise FoldError(error.reason, pointer=pointer + error.pointer,
                            code=getattr(error, "code", "SRV070")) from error
    return len(values)


def _apply_create(state, seen, prefixes, value):
    artifact = value["artifact"]
    identity = _artifact(artifact, "/artifact")
    if identity.id in seen:
        raise FoldError("creation_identity_exists", pointer="/artifact/id", code="SRV146")
    if prefixes and identity.id_prefix not in prefixes:
        raise FoldError("mixed_project_prefix", pointer="/artifact/id")
    # A create can supply relationships only once their ordered reducer exists.
    if artifact["relations"]:
        raise FoldError("create_relations_not_available", pointer="/artifact/relations")
    seen.add(identity.id)
    prefixes.add(identity.id_prefix)
    state[identity.id] = artifact
    return identity.id


def _apply_update(state, value):
    target = value["target"]
    if target not in state:
        raise FoldError("missing_operation_target", pointer="/target", code="SRV146")
    state[target] = preview_update(state[target], value).candidate
    return target


def _dispatch(state, seen, prefixes, value):
    kind = value["op"]
    if kind == "create":
        return _apply_create(state, seen, prefixes, value)
    if kind == "update":
        return _apply_update(state, value)
    raise FoldError("operation_requires_specialized_planner", pointer="/op")


def fold_operations(artifacts, operations, *, preconditions=(), source_files=None,
                    reserved_artifact_ids=()):
    """Fold the declared order over private values, returning one candidate per ID.

    Plan-wide preconditions address the supplied starting snapshot. Per-operation
    revision/hash guards address the immediately preceding intermediate artifact.
    Revisions are NOT advanced here. No intermediate or final artifact is stored.
    """
    try:
        state, seen, prefixes = _inventory(artifacts, reserved_artifact_ids)
        base = dict(state)
        ops = _owned_sequence(operations, "/operations")
        checked = _preflight(state, preconditions, _files(source_files))
        touched = {}
        for index, value in enumerate(ops):
            try:
                operation = ChangeOperation(value)
                target = _dispatch(state, seen, prefixes, operation.data)
                touched.setdefault(target, []).append(index)
            except ModelError as error:
                raise FoldError(error.reason, pointer="/operations/" + str(index) + error.pointer,
                    code=getattr(error, "code", "SRV070"), operation_index=index,
                    operations_completed=index) from error
        candidates = tuple(FoldedArtifact(target, _snapshot(state[target]),
            canonical_json_sha256(base[target]) if target in base else None,
            canonical_json_sha256(state[target]), tuple(touched[target]))
            for target in sorted(touched, key=lambda name: name.encode("utf-8")))
        ordered = [state[target] for target in sorted(state, key=lambda name: name.encode("utf-8"))]
        return OperationFold(_snapshot(ordered), candidates, len(ops), checked)
    except FoldError:
        raise
    except ModelError as error:
        raise FoldError(error.reason, pointer=error.pointer,
                        code=getattr(error, "code", "SRV070")) from error


def fold_plan_fields(plan, artifacts, *, observed_base_root, observed_scope,
                     source_files=None, reserved_artifact_ids=()):
    """Pre-metadata candidates from a self-hashed plan and explicit base observations.

    The caller supplies the actual scope/root observation; equality is not proof
    of its authenticity or of live storage. Declared final artifacts/root cannot
    yet be verified: metadata/lifecycle and full target validation follow later.
    """
    if type(plan) is not ChangePlan:
        raise FoldError("change_plan_required", pointer="/plan")
    if type(observed_base_root) is not str or re.fullmatch("[0-9a-f]{64}", observed_base_root) is None:
        raise FoldError("observed_base_root_required", pointer="/base/model_root_sha256")
    value = plan.data
    if observed_base_root != value["base"]["model_root_sha256"]:
        raise FoldError("base_root_mismatch", pointer="/base/model_root_sha256", code="SRV146")
    scope = _at("/base/scope_descriptor", ScopeDescriptor, observed_scope)
    if scope.data != value["base"]["scope_descriptor"]:
        raise FoldError("base_scope_mismatch", pointer="/base/scope_descriptor", code="SRV146")
    result = fold_operations(artifacts, value["operations"], preconditions=value["preconditions"],
        source_files=source_files, reserved_artifact_ids=reserved_artifact_ids)
    return replace(result, plan_sha256=plan.sha256)
