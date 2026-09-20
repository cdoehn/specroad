"""Passive minimum-rule contracts; no profile compiler or review selection."""
from dataclasses import dataclass
from ..model.errors import ModelError
from ..model.artifact_types import artifact_types
from ..model.artifact_schemas import MATURITIES
from .relation_types import require_relation_type
from .relations import SourceRelations

CORE_REQUIREMENT_MINIMA = (
    ("core:requirement-origin", ("addresses", "derived_from", "refines"), None),
    ("core:requirement-verification", ("verified_by",), ("test", "verification")),
)

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


