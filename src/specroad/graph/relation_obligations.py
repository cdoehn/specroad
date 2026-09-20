"""Minimum-relation gate inputs, not a lifecycle or review-status decision.

All approved requirements need provenance and a verification link (9.4/9.8,
SR-REQ-0061/0062). No waiver, priority, or text inference disables these minima.
"""
from dataclasses import dataclass

from ..model.errors import ModelError
from ..model.canonical import canonical_json_sha256
from .references import RelationReferences
from .indices import RelationIndex
from .relations import SourceRelations


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
        # Duplicate semantic edges do not invent a second distinct dependency.
        return len(self.endpoint_ids)

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

    def __init__(self, sources, *, profile_rules=()):
        if isinstance(sources, (str, bytes, dict)):
            raise ModelError("source_relations_sequence_required")
        try:
            sources = tuple(sources)
        except TypeError as error:
            raise ModelError("source_relations_sequence_required") from error
        refs = RelationReferences(sources)
        index = RelationIndex(refs)
        if profile_rules != ():
            raise ModelError("profile_relation_rules_not_supported_yet")
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
        object.__setattr__(self, "checks", tuple(checks))
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
