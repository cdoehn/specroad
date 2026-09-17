"""Stable public API for source-bound relation fields and update guards.

These APIs perform no writes and do not imply graph or lifecycle approval.
"""

from .relation_values import Relation, SourceRelations
from .relation_updates import (
    prepare_relation_update,
    require_relation_keys_unchanged,
    require_retained_relation_keys_unchanged,
)

__all__ = ["Relation", "SourceRelations", "prepare_relation_update",
           "require_relation_keys_unchanged", "require_retained_relation_keys_unchanged"]
