"""Hierarchy-cycle and local document-position checks over supplied records.

No files, caches, revision values or source records are changed. These checks do
not infer missing scope members, document ownership or include_document edges.
"""
from dataclasses import dataclass
import heapq

from ..model.errors import ModelError
from .references import RelationReferences, ResolvedRelation

HIERARCHY_RELATION_TYPES = ("refines", "part_of", "supersedes", "contains")


def _require_references(references):
    if type(references) is not RelationReferences:
        raise ModelError("relation_references_required")


def _has_cycle(edges):
    """Kahn traversal counts all nodes participating in this one edge type."""
    outgoing = {}
    indegree = {}
    for edge in edges:
        source, target = edge.source.id, edge.target.id
        outgoing.setdefault(source, []).append(target)
        indegree.setdefault(source, 0)
        indegree[target] = indegree.get(target, 0) + 1
    ready = [node for node, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    visited = 0
    while ready:
        source = heapq.heappop(ready)
        visited += 1
        for target in sorted(outgoing.get(source, ())):
            indegree[target] -= 1
            if indegree[target] == 0:
                heapq.heappush(ready, target)
    return visited != len(indegree)


def _cycle_witness(edges):
    """Find one deterministic directed cycle without recursive Python frames."""
    outgoing = {}
    for edge in edges:
        outgoing.setdefault(edge.source.id, []).append(edge)
        outgoing.setdefault(edge.target.id, [])
    for values in outgoing.values():
        values.sort(key=lambda edge: (edge.target.id, edge.relation.identity.id))
    finished = set()
    for root in sorted(outgoing):
        if root in finished:
            continue
        active = {root: 0}
        nodes = [root]
        path = []
        frames = [iter(outgoing[root])]
        while frames:
            edge = next(frames[-1], None)
            if edge is None:
                finished.add(nodes.pop())
                del active[next(reversed(active))]
                frames.pop()
                if path:
                    path.pop()
                continue
            target = edge.target.id
            if target in active:
                cycle = path[active[target]:] + [edge]
                first = min(range(len(cycle)), key=lambda index: cycle[index].source.id)
                return tuple(cycle[first:] + cycle[:first])
            if target not in finished:
                active[target] = len(nodes)
                nodes.append(target)
                path.append(edge)
                frames.append(iter(outgoing[target]))
    return None


class HierarchyCycleError(ModelError):
    """One blocking cycle with exact artifact/relation IDs, not inferred text."""

    def __init__(self, relation_type, edges):
        if (type(relation_type) is not str or relation_type not in HIERARCHY_RELATION_TYPES or type(edges) is not tuple
                or len(edges) < 2 or any(type(edge) is not ResolvedRelation for edge in edges)):
            raise ModelError("invalid_cycle_witness")
        if (any(edge.relation.type != relation_type for edge in edges)
                or any(edge.target != edges[(index + 1) % len(edges)].source for index, edge in enumerate(edges))
                or len({edge.source.id for edge in edges}) != len(edges)):
            raise ModelError("invalid_cycle_witness")
        super().__init__("relation_hierarchy_cycle", pointer="/relations")
        self.relation_type = relation_type
        self.artifact_ids = tuple(edge.source.id for edge in edges) + (edges[-1].target.id,)
        self.relation_ids = tuple(edge.relation.identity.id for edge in edges)

    def diagnostic(self):
        return {**super().diagnostic(), "relation_type": self.relation_type,
                "artifact_ids": list(self.artifact_ids), "relation_ids": list(self.relation_ids)}


@dataclass(frozen=True)
class HierarchyValidation:
    checked_relation_types: tuple
    source_count: int
    relation_count: int
    validation_scope: str = "hierarchies_only"


def validate_hierarchies(references):
    """Reject a cycle in each protected hierarchy, not the union of all types.

    A cycle in depends_on is not rejected by this local hierarchy policy. This
    is not a release readiness, scheduling or general graph-validity decision.
    """
    _require_references(references)
    for kind in HIERARCHY_RELATION_TYPES:
        edges = tuple(edge for edge in references.relations if edge.relation.type == kind)
        if _has_cycle(edges):
            raise HierarchyCycleError(kind, _cycle_witness(edges))
    return HierarchyValidation(HIERARCHY_RELATION_TYPES, len(references.sources), len(references.relations))


def contains_position_key(resolved):
    """Return the normative position/target/relation ordering key, not UI order."""
    if type(resolved) is not ResolvedRelation:
        raise ModelError("resolved_relation_required")
    if resolved.relation.type != "contains":
        raise ModelError("contains_relation_required")
    value = resolved.relation.data.get("position")
    # Follow the existing JSON integer contract: 0 and 0.0 both represent zero,
    # but a Boolean is not a position. Field construction rejects NaN/Infinity.
    if type(value) not in (int, float) or value < 0 or int(value) != value:
        raise ModelError("invalid_relation_position", pointer="/position")
    return value, resolved.target.id, resolved.relation.identity.id


def ordered_children(references, parent_id):
    """Return only outgoing contains edges for a known document or section.

    Sorting ties uses the complete target ID and then relation ID. Parent-count
    and document-inclusion validation are separate; this function only orders.
    """
    _require_references(references)
    if type(parent_id) is not str:
        raise ModelError("document_parent_id_required")
    parent = next((source for source in references.sources if source.id == parent_id), None)
    if parent is None:
        raise ModelError("unknown_document_parent")
    if parent.artifact_type not in ("document", "section"):
        raise ModelError("document_parent_type_required")
    children = (edge for edge in references.relations
                if edge.source.id == parent_id and edge.relation.type == "contains")
    return tuple(sorted(children, key=contains_position_key))
