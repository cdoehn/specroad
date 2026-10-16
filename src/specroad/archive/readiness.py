"""Read-only Release-Baseline admission while the M13 provider is unavailable.

Stored policy bytes are observations, not evaluated Evidence or release approval.
No caller callback, success label or prepared snapshot opens publication here.
"""
from dataclasses import dataclass

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.domain_schemas import validate_domain_fields
from ..model.errors import ModelError
from ..model.paths import artifact_path
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
    from ..changes.target_model import TargetModel
    if type(model) is not TargetModel:
        raise ModelError('baseline_target_model_required')
    model = model.snapshot()
    path = artifact_path('release', release_id, model.configuration.id_prefix)
    document = next((d for d in model.documents if d.path == path), None)
    if document is None:
        raise ModelError('baseline_release_missing', path=path)
    release = parse_json_object(document.content, path=path)
    validate_domain_fields(release, expected_type='release')
    stored = release['readiness_policy'].get('verification_evaluation')
    pointer = '/readiness_policy/verification_evaluation'
    if stored is not None and type(stored) is not dict:
        raise ModelError('release_evaluation_object_required', path=path, pointer=pointer)
    if evaluation is not None:
        if type(evaluation) is not dict:
            raise ModelError('release_evaluation_object_required', pointer='/evaluation')
        if stored is None:
            raise ModelError('stored_release_evaluation_required', path=path, pointer=pointer)
        if canonical_json_bytes(evaluation) != canonical_json_bytes(stored):
            raise ReleaseBaselineSelectionConflict('release_baseline_evaluation_conflict',
                path=path, pointer=pointer)
    value = {'format_version': 'release-baseline-readiness-v1', 'baseline_kind': 'release',
        'project_id': model.configuration.project_id, 'release_id': release_id,
        'release_revision': release['revision'], 'release_sha256': canonical_json_sha256(release),
        'stored_evaluation_present': stored is not None, 'stored_evaluation': stored,
        'stored_evaluation_sha256': None if stored is None else canonical_json_sha256(stored),
        'readiness_provider_available': False, 'readiness_evaluated': False,
        'stored_evaluation_validated': False, 'ready': False,
        'blockers': ([] if stored is not None else ['stored_release_evaluation_required'])
                    + ['release_readiness_provider_unavailable'],
        'validation_scope': 'stored_release_fields_and_unevaluated_policy_binding',
        'full_validation_passed': False, 'write_authorized': False, 'release_authorized': False}
    result = object.__new__(ReleaseBaselineReadiness)
    object.__setattr__(result, '_encoded', canonical_json_bytes(value))
    return result
