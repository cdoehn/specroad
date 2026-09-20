"""Immutable minimum observations, separate from graph traversal and policies."""
from dataclasses import dataclass

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


