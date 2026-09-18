"""Pure canonical relation preparation and non-normative inverse views.

No source artifact is edited. Canonicalization is an explicit preparation step,
not a relaxation of the normal immutable-key update guard. View construction
requires an already canonical input set; it never repairs stored data silently.
"""

from ..model.errors import ModelError
from .references import RelationReferences, ResolvedRelation
from .relations import Relation

SYMMETRIC_RELATION_TYPES = ("conflicts_with", "duplicates")


def _require_references(references):
    if type(references) is not RelationReferences:
        raise ModelError("relation_references_required")


def canonical_relation(resolved):
    """Return one source/target-canonical edge, preserving its relation ID.

    The returned value is only a proposal for later controlled authoring. No
    revision, audit information, external identity or extension is discarded.
    Directed relations are never reversed by this function.
    """
    if type(resolved) is not ResolvedRelation:
        raise ModelError("resolved_relation_required")
    if (resolved.relation.type not in SYMMETRIC_RELATION_TYPES
            or resolved.source.id < resolved.target.id):
        return resolved
    data = resolved.relation.data
    data["target"] = resolved.source.id
    return ResolvedRelation(Relation(resolved.target, data), resolved.target, resolved.source)


def canonical_relations(references):
    """Prepare a canonical tuple for all supplied records or reject duplicates.

    A pair cannot be stored twice, even with different relation IDs, metadata or
    directions. Nothing is merged or discarded to conceal that conflict.
    Completeness refers only to the supplied records, not an entire project.
    """
    _require_references(references)
    prepared = []
    seen = set()
    for original in references.relations:
        edge = canonical_relation(original)
        if edge.relation.type in SYMMETRIC_RELATION_TYPES:
            pair = (edge.relation.type, edge.source.id, edge.target.id)
            if pair in seen:
                raise ModelError("duplicate_symmetric_relation", pointer="/relations")
            seen.add(pair)
        prepared.append(edge)
    return tuple(sorted(prepared, key=lambda edge: edge.relation.key))


def require_canonical_relations(references):
    """Validate persisted orientation without modifying input bytes or values."""
    prepared = canonical_relations(references)
    originals = {edge.relation.identity.id: edge for edge in references.relations}
    for edge in prepared:
        if edge != originals[edge.relation.identity.id]:
            raise ModelError("noncanonical_symmetric_relation", pointer="/relations")
    return references



def require_canonical_reorder(previous, proposed):
    """Allow only the exact canonical preparation of the same logical edge.

    This narrowly checks the symmetry exception. It cannot authorize retargeting,
    changing relation kind/identity or sneaking metadata changes into a reorder.
    It is not an update or write permission; normal update guards stay strict.
    """
    from ..model.canonical import canonical_json_bytes

    if type(previous) is not ResolvedRelation or type(proposed) is not ResolvedRelation:
        raise ModelError("resolved_relation_required")
    expected = canonical_relation(previous)
    if (expected.source != proposed.source or expected.target != proposed.target
            or canonical_json_bytes(expected.relation.data) != canonical_json_bytes(proposed.relation.data)):
        raise ModelError("invalid_canonical_relation_reorder", pointer="/relations")
