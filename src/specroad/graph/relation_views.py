"""Non-normative traversal projections over explicitly resolved records."""

from dataclasses import dataclass

from ..model.errors import ModelError
from .references import ResolvedRelation
from ._symmetry import canonical_relation, require_canonical_relations

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

