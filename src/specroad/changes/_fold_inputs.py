"""Private source snapshots and initial preconditions, without operation effects."""
from ..model.canonical import canonical_json_sha256, canonical_json_bytes
from ..model._schema import validate_builtin
from ..model.errors import ModelError
from ..model.paths import project_path
from ..model.relation_values import RelationIdentity
from ..graph.relations import SourceRelations
from ..graph.references import RelationReferences
from ..graph.symmetry import require_canonical_relations
from ._common import _artifact, _reference, _at
from ._patch_values import _snapshot
from .schema import precondition_schema
from .folding_values import FoldError


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
