"""Minimum-relation gate inputs, not a lifecycle or review-status decision."""
from dataclasses import dataclass
from ..model.errors import ModelError
from ..model.canonical import canonical_json_sha256
from .references import RelationReferences
from .indices import RelationIndex
from ._obligation_rules import MinimumRelationRule, CORE_REQUIREMENT_MINIMA, _profile_rules
from .obligation_values import RelationObligationCheck


def _check(index, source, rule_id, minimum, severity, direction, types, target_types):
    views = [view for view in index.for_artifact(source.identity.id, direction=direction)
             if view.stored.relation.type in types
             and (not target_types or view.target.artifact_type in target_types)]
    return RelationObligationCheck(source.identity.id, rule_id, minimum,
        tuple(sorted({view.relation_id for view in views})),
        tuple(sorted({view.target.id for view in views})), severity, direction, types)


@dataclass(frozen=True, init=False)
class RelationObligations:
    """All checks over supplied records. A satisfied minimum is NOT current review."""
    checks: tuple
    input_sha256: str
    policy_sha256: str
    profile_rule_ids: tuple

    def __init__(self, sources, *, profile_rules=()):
        if isinstance(sources, (str, bytes, dict)):
            raise ModelError("source_relations_sequence_required")
        try:
            sources = tuple(sources)
        except TypeError as error:
            raise ModelError("source_relations_sequence_required") from error
        refs = RelationReferences(sources)
        index = RelationIndex(refs)
        rules = _profile_rules(profile_rules)
        checks = []
        for source in sorted(sources, key=lambda item: item.identity.id):
            if source.identity.artifact_type == "task" and source.data["maturity"] == "approved":
                # The stored link lives at the Requirement/Decision. A Task's
                # own scheduling/containment or a Capability alone is not it.
                checks.append(_check(index, source, "core:task-implementation", 1,
                    "error", "incoming", ("implemented_by",), ("requirement", "decision")))
            if source.identity.artifact_type != "requirement" or source.data["maturity"] != "approved":
                continue
            for rule_id, types, target_types in CORE_REQUIREMENT_MINIMA:
                checks.append(_check(index, source, rule_id, 1, "error", "outgoing", types, target_types))
        for source in sorted(sources, key=lambda item: item.identity.id):
            for rule in rules:
                if not rule.applies_to(source):
                    continue
                checks.append(_check(index, source, rule.rule_id, rule.minimum, rule.severity,
                                     rule.direction, rule.relation_types, rule.endpoint_types))
        object.__setattr__(self, "checks", tuple(sorted(checks, key=lambda item: (item.artifact_id, item.rule_id))))
        object.__setattr__(self, "policy_sha256", canonical_json_sha256([rule.data for rule in rules]))
        object.__setattr__(self, "profile_rule_ids", tuple(rule.rule_id for rule in rules))
        object.__setattr__(self, "input_sha256", canonical_json_sha256([
            source.data for source in sorted(sources, key=lambda item: item.identity.id)]))

    @property
    def diagnostics(self):
        return tuple(check.diagnostic() for check in self.checks if not check.satisfied)

    @property
    def requirements_satisfied(self):
        return all(check.satisfied for check in self.checks)

    @property
    def has_errors(self):
        return any(check.severity == "error" and not check.satisfied for check in self.checks)

    @property
    def validation_scope(self):
        return "minimum_relations_over_supplied_records"

    @property
    def approval_granted(self):
        return False

    @property
    def review_status_checked(self):
        return False

    @property
    def profile_composition_checked(self):
        return False
