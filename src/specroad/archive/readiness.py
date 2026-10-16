"""Read-only Release-Baseline admission while the M13 provider is unavailable.

Stored policy bytes are observations, not evaluated Evidence or release approval.
No caller callback, success label or prepared snapshot opens publication here.
"""
from dataclasses import dataclass

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object


class ReleaseBaselineSelectionConflict(ModelError):
    """An external selection cannot replace the Release's stored selection."""
    exit_code = 6


@dataclass(frozen=True, init=False)
class ReleaseBaselineReadiness:
    """Owned unavailable-provider observation; never a publication permit."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use assess_release_baseline_readiness with actual model bytes')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return canonical_json_sha256(self.data)

    def require_ready(self):
        # This remains closed even if someone modifies a detached report.
        raise ModelError('release_baseline_readiness_required')

    def __bool__(self):
        raise TypeError('Readiness observations are not release authority')


def assess_release_baseline_readiness(model, *, release_id, evaluation=None):
    """Bind actual stored release/policy bytes without evaluating readiness.

The descriptor's presence/hash does not claim that its schema, selected model
state, required runs or Evidence have been checked. M13 must implement that
complete service before any release creation can proceed.
"""
    from ._release_selection import bind_stored_release_selection
    selection = bind_stored_release_selection(model, release_id=release_id, evaluation=evaluation)
    value = {'format_version': 'release-baseline-readiness-v1', 'baseline_kind': 'release',
        **selection,
        'readiness_provider_available': False, 'readiness_evaluated': False,
        'stored_evaluation_validated': False, 'ready': False,
        'blockers': ([] if selection['stored_evaluation_present'] else ['stored_release_evaluation_required'])
                    + ['release_readiness_provider_unavailable'],
        'validation_scope': 'stored_release_fields_and_unevaluated_policy_binding',
        'full_validation_passed': False, 'write_authorized': False, 'release_authorized': False}
    result = object.__new__(ReleaseBaselineReadiness)
    object.__setattr__(result, '_encoded', canonical_json_bytes(value))
    return result
