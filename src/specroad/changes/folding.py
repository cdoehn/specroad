"""Ordered pure folding over private intermediate states, before metadata policy.

No external input is acquired or written. Unsupported specialized operations
fail explicitly; a field candidate is not an execution-ready Change Plan.
"""
from dataclasses import replace
import re
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ..graph.scope_descriptors import ScopeDescriptor
from ._common import _at
from .values import ChangePlan, ChangeOperation
from .folding_values import FoldError
from ._fold_inputs import _inventory, _relation_inventory, _owned_sequence, _preflight, _files
from ._fold_reducers import _dispatch
from ._fold_results import _finish

SUPPORTED_FOLD_OPERATIONS = ("create", "update", "relation_add", "relation_remove")


def fold_operations(artifacts, operations, *, preconditions=(), source_files=None,
                    reserved_artifact_ids=(), reserved_relation_ids=()):
    """Fold the declared order over private values, returning one candidate per ID.

    Plan-wide preconditions address the supplied starting snapshot. Per-operation
    revision/hash guards address the immediately preceding intermediate artifact.
    Revisions are NOT advanced here. No intermediate or final artifact is stored.
    """
    try:
        state, seen, prefixes = _inventory(artifacts, reserved_artifact_ids)
        used = _relation_inventory(state, reserved_relation_ids)
        base = dict(state)
        ops = _owned_sequence(operations, "/operations")
        checked = _preflight(state, preconditions, _files(source_files))
        touched = {}
        for index, value in enumerate(ops):
            try:
                operation = ChangeOperation(value)
                target = _dispatch(state, seen, prefixes, used, operation.data)
                touched.setdefault(target, []).append(index)
            except ModelError as error:
                raise FoldError(error.reason, pointer="/operations/" + str(index) + error.pointer,
                    code=getattr(error, "code", "SRV070"), operation_index=index,
                    operations_completed=index) from error
        return _finish(state, base, touched, len(ops), checked, hasher=canonical_json_sha256)
    except FoldError:
        raise
    except ModelError as error:
        raise FoldError(error.reason, pointer=error.pointer,
                        code=getattr(error, "code", "SRV070")) from error


def fold_plan_fields(plan, artifacts, *, observed_base_root, observed_scope,
                     source_files=None, reserved_artifact_ids=(), reserved_relation_ids=()):
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
    try:
        scope = _at("/base/scope_descriptor", ScopeDescriptor, observed_scope)
    except ModelError as error:
        raise FoldError(error.reason, pointer=error.pointer) from error
    if scope.data != value["base"]["scope_descriptor"]:
        raise FoldError("base_scope_mismatch", pointer="/base/scope_descriptor", code="SRV146")
    result = fold_operations(artifacts, value["operations"], preconditions=value["preconditions"],
        source_files=source_files, reserved_artifact_ids=reserved_artifact_ids,
        reserved_relation_ids=reserved_relation_ids)
    return replace(result, plan_sha256=plan.sha256)
