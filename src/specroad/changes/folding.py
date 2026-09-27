"""Ordered in-memory field evaluation; no metadata advancement or publication.

The caller must keep input containers stable while their private copies are made.
Specialized lifecycle/evidence/attachment/control operations are refused until
implemented by their own planner steps, never treated as successful no-ops.
"""
from dataclasses import replace
import re
from ..model.canonical import canonical_json_sha256, canonical_json_bytes
from ..model.identity_values import artifact_identity
from ..model.relation_values import RelationIdentity
from ..graph.relations import SourceRelations, Relation
from ..graph.references import RelationReferences, ResolvedRelation
from ..graph.symmetry import require_canonical_relations, canonical_relation, SYMMETRIC_RELATION_TYPES
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

SUPPORTED_FOLD_OPERATIONS = ("create", "update", "relation_add", "relation_remove")


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


def _relation_inventory(state, reserved_relation_ids):
    # All current edges are checked once; no file or graph provider is invoked.
    refs = _at("/artifacts", RelationReferences,
        tuple(SourceRelations(canonical_json_bytes(value)) for value in state.values()))
    _at("/artifacts", require_canonical_relations, refs)
    used = {edge.relation.identity.id for edge in refs.relations}
    for index, token in enumerate(_owned_sequence(reserved_relation_ids, "/reserved_relation_ids")):
        ident = _at("/reserved_relation_ids/" + str(index), RelationIdentity, token, "random128-v1")
        used.add(ident.id)
    return used


def _check_new_relations(artifact, state, used, pointer, *, single=False):
    identity = artifact_identity(artifact)
    pending, external_keys, pairs = set(), set(), set()
    for owner in state.values():
        for edge in owner["relations"]:
            external_keys.update(tuple(item[key] for key in ("source_system", "source_document", "external_id"))
                                 for item in edge["external_identities"])
            if edge["type"] in SYMMETRIC_RELATION_TYPES:
                pairs.add((edge["type"], owner["id"], edge["target"]))
    for index, value in enumerate(artifact["relations"]):
        where = pointer if single else pointer + "/" + str(index)
        relation = _at(where, Relation, identity, value)
        if relation.identity.id_scheme != "random128-v1":
            raise FoldError("new_relation_requires_random128", pointer=where + "/id_scheme")
        if relation.identity.id in used or relation.identity.id in pending:
            raise FoldError("relation_identity_exists", pointer=where + "/relation_id", code="SRV146")
        if relation.target not in state:
            raise FoldError("missing_relation_target", pointer=where + "/target", code="SRV146")
        resolved = _at(where, ResolvedRelation, relation, identity, artifact_identity(state[relation.target]))
        if canonical_relation(resolved) != resolved:
            raise FoldError("noncanonical_symmetric_relation", pointer=where)
        if relation.type in SYMMETRIC_RELATION_TYPES:
            pair = (relation.type, identity.id, relation.target)
            if pair in pairs:
                raise FoldError("duplicate_symmetric_relation", pointer=where)
            pairs.add(pair)
        for n, item in enumerate(value["external_identities"]):
            key = tuple(item[name] for name in ("source_system", "source_document", "external_id"))
            if key in external_keys:
                raise FoldError("duplicate_external_relation_identity", pointer=where + "/external_identities/" + str(n))
            external_keys.add(key)
        pending.add(relation.identity.id)
    used.update(pending)


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


def _apply_create(state, seen, prefixes, used, value):
    artifact = value["artifact"]
    identity = _artifact(artifact, "/artifact")
    if identity.id in seen:
        raise FoldError("creation_identity_exists", pointer="/artifact/id", code="SRV146")
    if prefixes and identity.id_prefix not in prefixes:
        raise FoldError("mixed_project_prefix", pointer="/artifact/id")
    _check_new_relations(artifact, state, used, "/artifact/relations")
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


def _apply_relation_add(state, used, value):
    source = value["source"]
    if source not in state:
        raise FoldError("missing_operation_source", pointer="/source", code="SRV146")
    # Validate only the new edge; never mutate the base list or fold result.
    proposal = {**state[source], "relations": [value["relation"]]}
    _check_new_relations(proposal, state, used, "/relation", single=True)
    candidate = {**state[source], "relations": [*state[source]["relations"], value["relation"]]}
    _artifact(candidate, "/source")
    state[source] = candidate
    return source


def _apply_relation_remove(state, value):
    source = value["source"]
    if source not in state:
        raise FoldError("missing_operation_source", pointer="/source", code="SRV146")
    old = state[source]
    matches = [edge for edge in old["relations"] if edge["relation_id"] == value["relation_id"]]
    if len(matches) != 1:
        raise FoldError("missing_operation_relation", pointer="/relation_id", code="SRV146")
    if canonical_json_sha256(matches[0]) != value["expected_sha256"]:
        raise FoldError("expected_relation_hash_mismatch", pointer="/expected_sha256", code="SRV146")
    candidate = {**old, "relations": [edge for edge in old["relations"] if edge["relation_id"] != value["relation_id"]]}
    _artifact(candidate, "/source")
    state[source] = candidate
    return source


def _dispatch(state, seen, prefixes, used, value):
    kind = value["op"]
    if kind == "create":
        return _apply_create(state, seen, prefixes, used, value)
    if kind == "update":
        return _apply_update(state, value)
    if kind == "relation_add":
        return _apply_relation_add(state, used, value)
    if kind == "relation_remove":
        return _apply_relation_remove(state, value)
    raise FoldError("operation_requires_specialized_planner", pointer="/op")


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
