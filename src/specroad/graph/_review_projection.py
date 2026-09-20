"""Exact Appendix J hash domains, separate from observation and review choice."""
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from .relations import Relation

CONTEXT_ALGORITHM = "relation_context_hash-v1"
# Appendix J.2: exclusions apply ONLY at the artifact top level.
CONTEXT_EXCLUDED_FIELDS = frozenset({
    "revision", "created_at", "created_by", "updated_at", "updated_by",
    "maturity", "implementation_status", "verification_plan_status",
    "risk_status", "validation_status", "issue_status", "proposal_status",
    "evidence_state", "baseline_state", "review_state", "relations", "tags",
})
RELATION_EXCLUDED_FIELDS = frozenset({"created_at", "created_by"})


def context_projection(value):
    return {key: item for key, item in value.items() if key not in CONTEXT_EXCLUDED_FIELDS}


def relation_content_sha256(relation):
    """Appendix J.1: omit creation audit only, NOT rationale or position."""
    if type(relation) is not Relation:
        raise ModelError("relation_required")
    return canonical_json_sha256({key: value for key, value in relation.data.items()
                                 if key not in RELATION_EXCLUDED_FIELDS})

