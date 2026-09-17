"""Resolve all stored edges in an explicitly supplied set of source records.

Missing targets are errors, including non-owning references. Partial-scope
boundary references, closure, adjacency indices, cycles and authoring are not
implemented by this input-set validator. No label or external ID is a target.
"""

from dataclasses import dataclass
from ..model.errors import ModelError
from ..model.identity_values import ArtifactIdentity
from .relations import Relation, SourceRelations
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


@dataclass(frozen=True)
class ResolvedRelation:
    relation: Relation
    source: ArtifactIdentity
    target: ArtifactIdentity

    def __post_init__(self):
        _check_endpoints(self.relation, self.source, self.target)


@dataclass(frozen=True, init=False)
class RelationReferences:
    """Complete result for provided records, not proof of a complete project.

    Missing-target and matrix validity are checked here. This object is not a
    lifecycle, content, review, schema or transaction approval.
    """
    sources: tuple
    relations: tuple
    validation_scope: str

    def __init__(self, sources):
        if isinstance(sources, (str, bytes, dict)):
            raise ModelError("source_relations_sequence_required")
        try:
            records = tuple(sources)
        except TypeError as error:
            raise ModelError("source_relations_sequence_required") from error
        index = {}
        prefix = None
        for source in records:
            if type(source) is not SourceRelations:
                raise ModelError("source_relations_required")
            if prefix is None:
                prefix = source.identity.id_prefix
            elif source.identity.id_prefix != prefix:
                raise ModelError("mixed_project_prefix", path=source.path)
            if source.identity.id in index:
                raise ModelError("duplicate_artifact_id", path=source.path, pointer="/id")
            index[source.identity.id] = source
        relations = []
        seen = set()
        for source in sorted(records, key=lambda record: record.identity.id):
            for position, relation in enumerate(source.relations):
                try:
                    if relation.identity.id in seen:
                        raise ModelError("duplicate_relation_id", pointer="/relation_id")
                    seen.add(relation.identity.id)
                    target = index.get(relation.target)
                    if target is None:
                        raise ModelError("missing_relation_target", pointer="/target")
                    relations.append(ResolvedRelation(relation, source.identity, target.identity))
                except ModelError as error:
                    error.path = source.path
                    error.pointer = "/relations/" + str(position) + error.pointer
                    raise
        object.__setattr__(self, "sources", tuple(index[name].identity for name in sorted(index)))
        object.__setattr__(self, "relations", tuple(sorted(relations, key=lambda item: item.relation.key)))
        object.__setattr__(self, "validation_scope", "relation_references_only")


def validate_relation_references(sources):
    return RelationReferences(sources)
