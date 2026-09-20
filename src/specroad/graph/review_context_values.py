"""Pure Appendix J projections; no review selection, approval, or writes.

These hashes bind values supplied by the caller. They are not signatures and
cannot prove source authenticity or a complete/current project observation.
"""
from dataclasses import dataclass

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ._review_projection import CONTEXT_ALGORITHM, context_projection, relation_content_sha256
from ..model.errors import ModelError
from .relations import Relation, SourceRelations
from .references import ResolvedRelation
from .symmetry import canonical_relation

@dataclass(frozen=True, init=False)
class EndpointReviewContext:
    """Full artifact hash and its distinct review-context hash, from one value."""
    artifact_id: str
    revision: int
    artifact_sha256: str
    canonical_bytes: bytes

    def __init__(self, source):
        if type(source) is not SourceRelations:
            raise ModelError("source_relations_required")
        data = source.data
        projection = context_projection(data)
        object.__setattr__(self, "artifact_id", source.identity.id)
        object.__setattr__(self, "revision", data["revision"])
        object.__setattr__(self, "artifact_sha256", canonical_json_sha256(data))
        object.__setattr__(self, "canonical_bytes", canonical_json_bytes(projection))

    @property
    def algorithm(self):
        return CONTEXT_ALGORITHM

    @property
    def context_sha256(self):
        from hashlib import sha256
        return sha256(self.canonical_bytes).hexdigest()

    @property
    def projection(self):
        import json
        return json.loads(self.canonical_bytes)


@dataclass(frozen=True, init=False)
class RelationReviewContext:
    """Observation of a stored relation and both endpoints, not a review record."""
    relation_id: str
    relation_sha256: str
    source: EndpointReviewContext
    target: EndpointReviewContext

    def __init__(self, relation, source, target):
        if type(source) is not SourceRelations or type(target) is not SourceRelations:
            raise ModelError("source_relations_required")
        if type(relation) is not Relation:
            raise ModelError("relation_required")
        resolved = ResolvedRelation(relation, source.identity, target.identity)
        if canonical_relation(resolved) != resolved:
            raise ModelError("noncanonical_symmetric_relation", pointer="/relations")
        retained = next((item for item in source.relations
                         if item.identity.id == relation.identity.id), None)
        if retained is None or retained.data != relation.data:
            raise ModelError("review_relation_not_in_source", path=source.path,
                             pointer="/relations")
        object.__setattr__(self, "relation_id", relation.identity.id)
        object.__setattr__(self, "relation_sha256", relation_content_sha256(relation))
        object.__setattr__(self, "source", EndpointReviewContext(source))
        object.__setattr__(self, "target", EndpointReviewContext(target))

    @property
    def validation_scope(self):
        return "relation_review_context_only"

    @property
    def review_selected(self):
        return False
