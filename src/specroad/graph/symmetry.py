"""Pure canonical relation preparation and non-normative inverse views.

No source artifact is edited. Canonicalization is an explicit preparation step,
not a relaxation of the normal immutable-key update guard. View construction
requires an already canonical input set; it never repairs stored data silently.
"""

from dataclasses import dataclass

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


@dataclass(frozen=True)
class RelationView:
    """Computed traversal of one stored edge; never a second normative edge."""
    stored: ResolvedRelation
    inverse: bool = False

    def __post_init__(self):
        if type(self.stored) is not ResolvedRelation or type(self.inverse) is not bool:
            raise ModelError("invalid_relation_view")
        if canonical_relation(self.stored) != self.stored:
            raise ModelError("noncanonical_symmetric_relation", pointer="/relations")

    @property
    def source(self):
        return self.stored.target if self.inverse else self.stored.source

    @property
    def target(self):
        return self.stored.source if self.inverse else self.stored.target

    @property
    def type(self):
        kind = self.stored.relation.type
        return "superseded_by" if self.inverse and kind == "supersedes" else kind

    @property
    def relation_id(self):
        return self.stored.relation.identity.id

    @property
    def normative(self):
        return False


@dataclass(frozen=True, init=False)
class RelationViews:
    """Read-only traversal over one explicitly supplied, resolved relation set.

    Direction is relative to physical storage: incoming views reverse source
    and target, with ``inverse=True``. For directed kinds without a named inverse
    the stored type is retained and the direction flag carries that distinction.
    This does not build or claim a complete incoming project index (step 3.e).
    """
    sources: tuple
    stored_relations: tuple
    validation_scope: str

    def __init__(self, references):
        require_canonical_relations(references)
        object.__setattr__(self, "sources", references.sources)
        object.__setattr__(self, "stored_relations", references.relations)
        object.__setattr__(self, "validation_scope", "canonical_relations_and_views_only")

    def for_artifact(self, artifact_id, *, direction="both"):
        if type(artifact_id) is not str or artifact_id not in {source.id for source in self.sources}:
            raise ModelError("unknown_relation_view_artifact")
        if type(direction) is not str or direction not in ("outgoing", "incoming", "both"):
            raise ModelError("invalid_relation_view_direction")
        views = []
        for edge in self.stored_relations:
            if edge.source.id == artifact_id and direction in ("outgoing", "both"):
                views.append(RelationView(edge))
            if edge.target.id == artifact_id and direction in ("incoming", "both"):
                views.append(RelationView(edge, inverse=True))
        return tuple(sorted(views, key=lambda view: (view.type, view.target.id, view.relation_id, view.inverse)))


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
