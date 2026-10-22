"""Own actual Release selection bytes; no readiness service or write permission."""
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.domain_schemas import validate_domain_fields
from ..model.errors import ModelError
from ..model.paths import artifact_path
from ..storage.json_syntax import parse_json_object


def bind_stored_release_selection(model, *, release_id, evaluation):
    """Resolve stored precedence before the separate readiness admission gate."""
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
        same = canonical_json_bytes(evaluation) == canonical_json_bytes(stored)
        if not same:
            # Compare valid descriptors by the established native normalization,
            # as release readiness does. Keep the original stored value/hash for
            # the archive; reading must not migrate or reorder legacy policy data.
            from ..verification.evaluation import VerificationEvaluation
            try:
                same = (VerificationEvaluation(canonical_json_bytes(evaluation)).canonical_bytes
                        == VerificationEvaluation(canonical_json_bytes(stored)).canonical_bytes)
            except ModelError:
                # Unsupported historical objects retain exact-value comparison;
                # a malformed alternative cannot silently replace stored data.
                same = False
        if not same:
            from .readiness import ReleaseBaselineSelectionConflict
            raise ReleaseBaselineSelectionConflict('release_baseline_evaluation_conflict',
                path=path, pointer=pointer)
    return {'project_id': model.configuration.project_id, 'release_id': release_id,
        'release_revision': release['revision'], 'release_sha256': canonical_json_sha256(release),
        'stored_evaluation_present': stored is not None, 'stored_evaluation': stored,
        'stored_evaluation_sha256': None if stored is None else canonical_json_sha256(stored)}
