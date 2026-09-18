"""Immutable adjacency over an explicitly supplied, resolved relation set.

This in-memory index proves coverage of its input, not coverage of a project.
Use the project-bound reader for current incoming/outgoing project relations.
"""
from dataclasses import dataclass
from types import MappingProxyType

from ..model.errors import ModelError
from .references import RelationReferences
from .relation_views import RelationView
from .symmetry import require_canonical_relations


def _query_arguments(artifact_id, direction, identities):
    if type(artifact_id) is not str or artifact_id not in identities:
        raise ModelError("unknown_relation_view_artifact")
    if type(direction) is not str or direction not in ("incoming", "outgoing", "both"):
        raise ModelError("invalid_relation_view_direction")


def _view_key(view):
    return view.type, view.target.id, view.relation_id, view.inverse


@dataclass(frozen=True, init=False)
class RelationIndex:
    """Both physical directions; each edge retains its one normative identity."""
    references: RelationReferences
    _outgoing: object
    _incoming: object

    def __init__(self, references):
        require_canonical_relations(references)
        outgoing = {source.id: [] for source in references.sources}
        incoming = {source.id: [] for source in references.sources}
        for edge in references.relations:
            outgoing[edge.source.id].append(RelationView(edge))
            incoming[edge.target.id].append(RelationView(edge, inverse=True))
        object.__setattr__(self, "references", references)
        object.__setattr__(self, "_outgoing", MappingProxyType({
            name: tuple(sorted(values, key=_view_key)) for name, values in outgoing.items()}))
        object.__setattr__(self, "_incoming", MappingProxyType({
            name: tuple(sorted(values, key=_view_key)) for name, values in incoming.items()}))

    @property
    def validation_scope(self):
        return "supplied_relation_set_only"

    def for_artifact(self, artifact_id, *, direction="both"):
        _query_arguments(artifact_id, direction, self._outgoing)
        if direction == "outgoing":
            return self._outgoing[artifact_id]
        if direction == "incoming":
            return self._incoming[artifact_id]
        return tuple(sorted(self._outgoing[artifact_id] + self._incoming[artifact_id], key=_view_key))
