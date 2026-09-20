"""Minimum-relation gate inputs, not a lifecycle or review-status decision.

All approved requirements need provenance and a verification link (9.4/9.8,
SR-REQ-0061/0062). No waiver, priority, or text inference disables these minima.
"""
from dataclasses import dataclass

from ..model.errors import ModelError
from ..model.artifact_types import artifact_types
from ..model.artifact_schemas import MATURITIES
from .relation_types import require_relation_type
from ..model.canonical import canonical_json_sha256
from .references import RelationReferences
from .indices import RelationIndex
from .relations import SourceRelations


_ALL_TYPES = frozenset(item.artifact_type for item in artifact_types())
_MATURITIES = frozenset(MATURITIES)


def _tokens(value, allowed, field, *, nonempty=True):
    if type(value) not in (tuple, list) or (nonempty and not value):
        raise ModelError("invalid_minimum_relation_rule", pointer="/" + field)
    if any(type(item) is not str or item not in allowed for item in value):
        raise ModelError("invalid_minimum_relation_rule", pointer="/" + field)
    if len(set(value)) != len(value):
        raise ModelError("duplicate_minimum_relation_filter", pointer="/" + field)
    return tuple(sorted(value))


@dataclass(frozen=True, init=False)
class MinimumRelationRule:
    """A pre-resolved profile minimum, NOT an executable SRX condition.

    Effective profile composition/selection belongs to the caller. Core minima
    are always added and cannot be disabled by an empty or permissive profile.
    Counts refer to distinct stored relations; endpoint_ids are explanatory.
    """
    rule_id: str
    artifact_types: tuple
    maturities: tuple
    relation_types: tuple
    endpoint_types: tuple
    direction: str
    minimum: int
    severity: str

    def __init__(self, rule_id, *, artifact_types, relation_types, minimum=1,
                 maturities=(), endpoint_types=(), direction="outgoing", severity="error"):
        if type(rule_id) is not str or not rule_id.strip() or rule_id.startswith("core:"):
            raise ModelError("invalid_profile_relation_rule_id")
        if type(minimum) is not int or minimum < 0:
            raise ModelError("invalid_minimum_relation_count")
        if type(direction) is not str or direction not in ("outgoing", "incoming", "both"):
            raise ModelError("invalid_minimum_relation_direction")
        if type(severity) is not str or severity not in ("info", "warning", "error"):
            raise ModelError("invalid_minimum_relation_severity")
        if type(relation_types) not in (tuple, list) or not relation_types:
            raise ModelError("invalid_minimum_relation_types")
        for kind in relation_types:
            require_relation_type(kind)
        values = {
            "rule_id": rule_id, "minimum": minimum, "direction": direction, "severity": severity,
            "artifact_types": _tokens(artifact_types, _ALL_TYPES, "artifact_types"),
            "maturities": _tokens(maturities, _MATURITIES, "maturities", nonempty=False),
            "relation_types": _tokens(relation_types, frozenset(relation_types), "relation_types"),
            "endpoint_types": _tokens(endpoint_types, _ALL_TYPES, "endpoint_types", nonempty=False),
        }
        for key, value in values.items():
            object.__setattr__(self, key, value)

    @property
    def data(self):
        return {"rule_id": self.rule_id, "minimum": self.minimum,
                "direction": self.direction, "severity": self.severity,
                "artifact_types": list(self.artifact_types), "maturities": list(self.maturities),
                "relation_types": list(self.relation_types), "endpoint_types": list(self.endpoint_types)}

    def applies_to(self, source):
        if type(source) is not SourceRelations:
            raise ModelError("source_relations_required")
        return (source.identity.artifact_type in self.artifact_types
                and (not self.maturities or source.data["maturity"] in self.maturities))


def _profile_rules(value):
    if isinstance(value, (str, bytes, dict)):
        raise ModelError("profile_relation_rules_sequence_required")
    try:
        rules = tuple(value)
    except TypeError as error:
        raise ModelError("profile_relation_rules_sequence_required") from error
    if any(type(rule) is not MinimumRelationRule for rule in rules):
        raise ModelError("minimum_relation_rule_required")
    if len({rule.rule_id for rule in rules}) != len(rules):
        raise ModelError("duplicate_profile_relation_rule_id")
    return tuple(sorted(rules, key=lambda rule: rule.rule_id))


@dataclass(frozen=True)
class RelationObligationCheck:
    artifact_id: str
    rule_id: str
    minimum: int
    relation_ids: tuple
    endpoint_ids: tuple
    severity: str
    direction: str
    relation_types: tuple

    @property
    def actual(self):
        # Count stored relation identities, never a second inverse copy.
        return len(self.relation_ids)

    @property
    def satisfied(self):
        return self.actual >= self.minimum

    def diagnostic(self):
        if self.satisfied:
            return None
        return {"reason": "missing_required_relation", "artifact_id": self.artifact_id,
                "rule_id": self.rule_id, "severity": self.severity,
                "minimum": self.minimum, "actual": self.actual,
                "direction": self.direction, "relation_types": list(self.relation_types),
                "relation_ids": list(self.relation_ids), "endpoint_ids": list(self.endpoint_ids)}


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
            if source.identity.artifact_type != "requirement" or source.data["maturity"] != "approved":
                continue
            for rule_id, types, target_types in (
                ("core:requirement-origin", ("addresses", "derived_from", "refines"), None),
                ("core:requirement-verification", ("verified_by",), ("test", "verification")),
            ):
                views = [view for view in index.for_artifact(source.identity.id, direction="outgoing")
                         if view.type in types and (target_types is None
                                                   or view.target.artifact_type in target_types)]
                checks.append(RelationObligationCheck(source.identity.id, rule_id, 1,
                    tuple(sorted(view.relation_id for view in views)),
                    tuple(sorted({view.target.id for view in views})), "error", "outgoing", types))
        for source in sorted(sources, key=lambda item: item.identity.id):
            for rule in rules:
                if not rule.applies_to(source):
                    continue
                views = [view for view in index.for_artifact(source.identity.id, direction=rule.direction)
                         if view.stored.relation.type in rule.relation_types
                         and (not rule.endpoint_types or view.target.artifact_type in rule.endpoint_types)]
                checks.append(RelationObligationCheck(source.identity.id, rule.rule_id, rule.minimum,
                    tuple(sorted({view.relation_id for view in views})),
                    tuple(sorted({view.target.id for view in views})), rule.severity,
                    rule.direction, rule.relation_types))
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
