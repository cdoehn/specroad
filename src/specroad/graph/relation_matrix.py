"""Compatibility API backed by the single Core relation registry.

No separate parser, import or authoring-specific copy of the matrix exists.
"""

from .relation_types import RelationRule, relation_rules, relation_pair_allowed

__all__ = ["RelationRule", "relation_rules", "relation_pair_allowed"]
