"""Resolve all stored edges in an explicitly supplied set of source records.

Missing targets are errors, including non-owning references. Partial-scope
boundary references, closure, adjacency indices, cycles and authoring are not
implemented by this input-set validator. No label or external ID is a target.
"""

from dataclasses import dataclass
from ..model.errors import ModelError
from ..model.identity_values import ArtifactIdentity
from .relations import Relation, SourceRelations
from .relation_matrix import relation_pair_allowed  # Preserve the earlier import path.
from ._reference_checks import (
    _check_endpoints, _source_identity_errors, _relation_identity_errors,
    _target_identity, _locate_relation_error,
)


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
            for error in _source_identity_errors(source, index, prefix):
                raise error
            index[source.identity.id] = source
        relations = []
        seen = set()
        external_keys = set()
        for source in sorted(records, key=lambda record: record.identity.id):
            for position, relation in enumerate(source.relations):
                try:
                    for error in _relation_identity_errors(relation, seen, external_keys):
                        raise error
                    target = _target_identity(relation, index)
                    relations.append(ResolvedRelation(relation, source.identity, target))
                except ModelError as error:
                    raise _locate_relation_error(error, source, position)
        object.__setattr__(self, "sources", tuple(index[name].identity for name in sorted(index)))
        object.__setattr__(self, "relations", tuple(sorted(relations, key=lambda item: item.relation.key)))
        object.__setattr__(self, "validation_scope", "relation_references_only")


def validate_relation_references(sources):
    return RelationReferences(sources)
