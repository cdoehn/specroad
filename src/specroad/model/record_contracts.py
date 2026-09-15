"""Typed descriptors shared by passive readers and future workflow services.

Only compiled core types are registered here. A descriptor neither grants a
write capability nor confirms the integrity or approval of a loaded record.
"""

from dataclasses import dataclass
from types import MappingProxyType

from .errors import ModelError
from .versions import SCHEMA_VERSION

RECORD_TYPES = (
    "source", "verification", "test", "evidence", "baseline", "proposal", "issue",
    "document", "section", "content_block", "view", "code_ref", "relation_review", "configuration",
)
VALIDATION_SCOPE = "record_fields_only"
SPECIAL_STATES = {
    "evidence": ("evidence_state", {"recorded": "approved"}),
    "baseline": ("baseline_state", {"sealed": "approved"}),
    "relation_review": ("review_state", {"recorded": "approved"}),
    "proposal": ("proposal_status", {
        "draft": "draft", "validated": "proposed", "checked": "proposed",
        "in_review": "in_review", "approved": "approved", "applied": "approved",
        "rejected": "rejected", "stale": "retired",
    }),
}

@dataclass(frozen=True)
class RecordContract:
    artifact_type: str
    schema_id: str
    validation_scope: str
    status_field: str | None
    state_maturities: tuple[tuple[str, str], ...]

    @property
    def requires_specialized_operation(self) -> bool:
        return self.status_field is not None


def _make_contract(kind: str) -> RecordContract:
    field, states = SPECIAL_STATES.get(kind, (None, {}))
    return RecordContract(kind, "urn:specroad:schema:" + SCHEMA_VERSION + ":artifact-record:" + kind,
                          VALIDATION_SCOPE, field, tuple(states.items()))


_CONTRACTS = MappingProxyType({kind: _make_contract(kind) for kind in RECORD_TYPES})


def record_contract(kind: str) -> RecordContract:
    """Resolve an immutable descriptor without a graph or executable adapter."""
    if type(kind) is not str or kind not in _CONTRACTS:
        raise ModelError("record_type_not_supported", pointer="/artifact_type")
    return _CONTRACTS[kind]
