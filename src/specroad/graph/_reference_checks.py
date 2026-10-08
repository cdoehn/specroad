"""Shared reference predicates; callers choose strict or diagnostic traversal.

Identity generators update only caller-owned lookup sets. A strict consumer
stops at its first yielded error; an observer can retain all independent errors.
Neither traversal constructs a partially valid graph or invents target values.
"""

from ..model.errors import ModelError
from ..model.identity_values import ArtifactIdentity
from .relations import Relation
from .relation_matrix import relation_pair_allowed


def _check_endpoints(relation, source, target):
    if type(relation) is not Relation or type(source) is not ArtifactIdentity or type(target) is not ArtifactIdentity:
        raise ModelError("relation_endpoint_values_required")
    if relation.source != source or relation.target != target.id:
        raise ModelError("relation_endpoint_identity_mismatch")
    if source.id_prefix != target.id_prefix:
        raise ModelError("mixed_project_prefix")
    if source.id == target.id:
        raise ModelError("self_relation_forbidden", pointer="/target")
    if not relation_pair_allowed(relation.type, source.artifact_type, target.artifact_type):
        raise ModelError("relation_type_pair_forbidden", pointer="/target")


def _source_identity_errors(source, index, prefix):
    if source.identity.id_prefix != prefix:
        yield ModelError("mixed_project_prefix", path=source.path)
    if source.identity.id in index:
        yield ModelError("duplicate_artifact_id", path=source.path, pointer="/id")


def _relation_identity_errors(relation, seen, external_keys):
    if relation.identity.id in seen:
        yield ModelError("duplicate_relation_id", pointer="/relation_id")
    seen.add(relation.identity.id)
    for position, external in enumerate(relation.data["external_identities"]):
        key = tuple(external[name] for name in ("source_system", "source_document", "external_id"))
        if key in external_keys:
            yield ModelError("duplicate_external_relation_identity",
                             pointer="/external_identities/" + str(position))
        external_keys.add(key)


def _target_identity(relation, index):
    target = index.get(relation.target)
    if target is None:
        raise ModelError("missing_relation_target", pointer="/target")
    return target.identity


def _locate_relation_error(error, source, position):
    error.path = source.path
    error.pointer = "/relations/" + str(position) + error.pointer
    return error
