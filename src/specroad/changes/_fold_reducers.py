"""Fixed field/relation reducers. No registration from data and no file effects."""
from ..model.canonical import canonical_json_sha256
from ..model.identity_values import artifact_identity
from ..graph.relations import Relation
from ..graph.references import ResolvedRelation
from ..graph.symmetry import canonical_relation, SYMMETRIC_RELATION_TYPES
from ._common import _artifact, _at
from .update_preview import preview_update
from .folding_values import FoldError


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
