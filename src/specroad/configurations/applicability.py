"""Immutable applicability results over the pure scope classification stage."""
from dataclasses import dataclass

from ._applicability_scope import classify_applicability


@dataclass(frozen=True, init=False)
class ApplicabilityResult:
    """A source-bound classification, before project scope closure or gates."""
    artifact_id: str
    status: str
    reason: str
    configuration_id: str | None
    configuration_sha256: str | None
    source_sha256: str

    def __init__(self, record, configuration=None, *, require_configuration=False):
        decision = classify_applicability(record, configuration, require_configuration=require_configuration)
        for key, value in decision.items():
            object.__setattr__(self, key, value)

    def __bool__(self):
        raise TypeError('Applicability classifications require an explicit status check.')

    @property
    def data(self):
        return {key: getattr(self, key) for key in ('artifact_id', 'status', 'reason', 'configuration_id',
                                                  'configuration_sha256', 'source_sha256')}

    @property
    def validation_scope(self):
        return 'supplied_artifact_applicability_only'


def evaluate_applicability(record, configuration=None, *, require_configuration=False):
    """Classify one stored artifact without loading a project or choosing defaults."""
    return ApplicabilityResult(record, configuration, require_configuration=require_configuration)
