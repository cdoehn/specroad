"""Stored Core relation vocabulary. Inverse views are not stored edges."""

from ..model.errors import ModelError

CORE_RELATION_TYPES = (
    "addresses", "refines", "derived_from", "depends_on", "conflicts_with",
    "constrains", "allocated_to", "implemented_by", "verified_by", "produces",
    "mitigates", "scheduled_for", "part_of", "supersedes", "duplicates",
    "contains", "references",
)


def require_relation_type(value):
    if type(value) is not str or value not in CORE_RELATION_TYPES:
        raise ModelError("unknown_stored_relation_type", pointer="/type")
    return value
