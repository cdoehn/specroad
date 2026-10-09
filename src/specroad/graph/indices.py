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

    @classmethod
    def from_order(cls, references, order):
        """Validate an untrusted ordering against every fresh resolved edge.

        The hint supplies IDs only. Values always come from ``references``;
        even a self-consistently rehashed cache cannot remove or invent edges.
        Validation is linear in the supplied complete adjacency, without sorting.
        """
        require_canonical_relations(references)
        if type(order) is not dict or set(order) != {"outgoing", "incoming"}:
            raise ModelError("invalid_relation_order")
        sources = {source.id for source in references.sources}
        edges = {edge.relation.identity.id: edge for edge in references.relations}
        tables = {}
        for direction, inverse in (("outgoing", False), ("incoming", True)):
            table = order[direction]
            if type(table) is not dict or set(table) != sources:
                raise ModelError("invalid_relation_order")
            seen = set()
            checked = {}
            for source, names in table.items():
                if type(names) is not list:
                    raise ModelError("invalid_relation_order")
                values = []
                previous = None
                for name in names:
                    if type(name) is not str or name not in edges or name in seen:
                        raise ModelError("invalid_relation_order")
                    view = RelationView(edges[name], inverse=inverse)
                    key = _view_key(view)
                    if view.source.id != source or (previous is not None and key < previous):
                        raise ModelError("invalid_relation_order")
                    values.append(view)
                    seen.add(name)
                    previous = key
                checked[source] = tuple(values)
            if seen != set(edges):
                raise ModelError("invalid_relation_order")
            tables[direction] = MappingProxyType(checked)
        result = object.__new__(cls)
        object.__setattr__(result, "references", references)
        object.__setattr__(result, "_outgoing", tables["outgoing"])
        object.__setattr__(result, "_incoming", tables["incoming"])
        return result

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
