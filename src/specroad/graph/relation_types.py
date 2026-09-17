"""Single immutable Core relation registry for field and endpoint validation.

This validator never guesses an edge from labels or text and never reverses a
stored edge. In particular, refines always points from detailed to general.
"""

from dataclasses import dataclass
from ..model.artifact_types import artifact_type, artifact_types
from ..model.errors import ModelError


@dataclass(frozen=True)
class RelationRule:
    kind: str
    sources: frozenset
    targets: frozenset
    same_type: bool = False

    def accepts(self, source, target):
        return source in self.sources and target in self.targets and (not self.same_type or source == target)


def _rule(kind, sources, targets, same_type=False):
    return RelationRule(kind, frozenset(sources.split()), frozenset(targets.split()), same_type)


_ALL = " ".join(item.artifact_type for item in artifact_types())
_DEPENDENCY = "capability requirement component interface task release milestone code_ref configuration"
_RULES = (
    _rule("addresses", "need capability requirement", "goal"),
    _rule("refines", "need", "goal need"),
    _rule("refines", "capability", "need capability"),
    _rule("refines", "requirement", "need capability requirement"),
    _rule("refines", "scenario", "need capability requirement scenario"),
    _rule("derived_from", "goal need capability requirement scenario decision risk assumption component interface verification test release milestone task term document section content_block view code_ref configuration", "source need decision assumption"),
    _rule("depends_on", _DEPENDENCY, _DEPENDENCY),
    _rule("conflicts_with", _ALL, _ALL),
    _rule("constrains", "requirement decision", "capability requirement component interface"),
    _rule("allocated_to", "requirement", "component interface"),
    _rule("implemented_by", "capability requirement decision", "task component code_ref"),
    _rule("verified_by", "requirement capability task", "verification test"),
    _rule("produces", "verification test", "evidence"),
    _rule("mitigates", "requirement decision task", "risk"),
    _rule("scheduled_for", "capability requirement task", "release milestone"),
    _rule("part_of", "milestone", "release"),
    _rule("part_of", "component", "component capability"),
    _rule("part_of", "interface", "component capability"),
    _rule("part_of", "task", "release milestone capability"),
    _rule("supersedes", _ALL, _ALL, True),
    _rule("duplicates", _ALL, _ALL, True),
    _rule("contains", "document", "section"),
    _rule("contains", "section", "section content_block"),
    _rule("references", "content_block view verification test source", _ALL),
)


CORE_RELATION_TYPES = tuple(dict.fromkeys(row.kind for row in _RULES))


def require_relation_type(value):
    if type(value) is not str or value not in CORE_RELATION_TYPES:
        raise ModelError("unknown_stored_relation_type", pointer="/type")
    return value


def relation_rules(kind):
    """Return immutable rules for a known stored type, never a fallback rule."""
    require_relation_type(kind)
    return tuple(row for row in _RULES if row.kind == kind)


def relation_pair_allowed(kind, source_type, target_type):
    """Exactly one matching row permits a pair. Identity self-links are separate."""
    require_relation_type(kind)
    artifact_type(source_type)
    artifact_type(target_type)
    return sum(row.accepts(source_type, target_type) for row in relation_rules(kind)) == 1
