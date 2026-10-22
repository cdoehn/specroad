"""Restore a read-only Release input from a separately bound Work object."""
from hashlib import sha256

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from ..verification.evaluation import VerificationEvaluation
from ..verification.read_input import VerificationReadBindingConflict
from .readiness import ReleaseReadinessContext


def resume_release_readiness_context(model, raw, *, expected_sha256,
        scope_bindings, inputs=None, input_roles=None, waiver_reviews=None,
        waiver_verifier=None):
    """Re-evaluate saved selection/time, never deserialize a readiness pass.

    The caller obtains bytes and their independent hash from the native Work
    input store. Model, product inputs and trusted services must be supplied
    from the preserved source snapshot. No saved path or callback is opened.
    """
    if (type(raw) is not bytes or type(expected_sha256) is not str
            or len(expected_sha256) != 64
            or any(c not in '0123456789abcdef' for c in expected_sha256)):
        raise ModelError('readiness_work_input_binding_required')
    if sha256(raw).hexdigest() != expected_sha256:
        raise VerificationReadBindingConflict('readiness_work_input_changed')
    data = parse_json_object(raw)
    if (set(data) != {'format_version', 'release_id', 'configuration_id',
            'evaluation', 'evaluation_sha256', 'evaluated_at', 'input_sha256'}
            or data['format_version'] != 'release-readiness-work-input-v1'
            or canonical_json_bytes(data) != raw):
        raise ModelError('readiness_work_input_invalid')
    evaluation = (None if data['evaluation'] is None else
                  VerificationEvaluation(canonical_json_bytes(data['evaluation'])))
    if data['evaluation_sha256'] != (None if evaluation is None else evaluation.sha256):
        raise VerificationReadBindingConflict('readiness_work_evaluation_changed')
    restored = ReleaseReadinessContext(model, data['release_id'],
        scope_bindings=scope_bindings, evaluated_at=data['evaluated_at'],
        configuration_id=data['configuration_id'], evaluation=evaluation,
        inputs=inputs, input_roles=input_roles, waiver_reviews=waiver_reviews,
        waiver_verifier=waiver_verifier)
    if restored.work_input != raw:
        raise VerificationReadBindingConflict('readiness_work_observation_changed')
    return restored
