"""Shared evaluation selection and detached projections for read adapters.

Callers retain model/scope/input admission and public error types. These
helpers perform no discovery, I/O, execution or readiness authorization.
"""
from hashlib import sha256

from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from .evaluation import VerificationEvaluation, VerificationEvaluationError


def resolve_read_evaluation(model, evaluation, descriptor, *, conflict_type):
    """Own the explicit descriptor before resolving stored Release precedence.

    model is the caller's native snapshot; conflict_type is its public exception
    class, supplied by trusted adapter code, never by serialized read input.
    """
    if evaluation is not None:
        if type(evaluation) is not VerificationEvaluation:
            raise VerificationEvaluationError('typed_verification_evaluation_required')
        evaluation = VerificationEvaluation(evaluation.source_bytes)
    if descriptor is None:
        return evaluation, None
    from ..graph.scope_descriptors import ScopeDescriptor
    if type(descriptor) is not ScopeDescriptor:
        raise ModelError('verification_scope_descriptor_required')
    scope = descriptor.data
    base = scope['selector']['base_scope_descriptor'] if scope['scope_kind'] == 'configuration' else scope
    if base['scope_kind'] != 'release':
        return evaluation, None
    from ..archive._release_selection import bind_stored_release_selection
    release = bind_stored_release_selection(model,
        release_id=base['selector']['release_id'], evaluation=None)
    stored = release['stored_evaluation']
    if stored is not None:
        stored = VerificationEvaluation(canonical_json_bytes(stored))
        if evaluation is not None and evaluation.sha256 != stored.sha256:
            raise conflict_type('verification_release_evaluation_conflict')
        evaluation = stored
    return evaluation, {**release, 'selection_origin': 'stored' if stored is not None else
        'explicit_provisional' if evaluation is not None else 'missing',
        'provisional': stored is None, 'release_authorized': False}


def record_bindings(records):
    if type(records) not in (tuple, list) or any(type(r) is not SourceRelations for r in records):
        raise ModelError('verification_query_sources_required')
    rows = [{'id': r.identity.id, 'sha256': sha256(r.source_bytes).hexdigest()} for r in records]
    return sorted(rows, key=lambda row: row['id'].encode('utf-8'))


def computed_results(data):
    """Project the already checked native aggregation without changing records."""
    return {row['subject_artifact_id']: row['verification_result']
            for row in data['aggregation']['subjects']}


def matching_currentness_verification(expected, supplied):
    """Reuse the bound native provider after the caller's model/record checks."""
    if supplied is not None and (type(supplied) is not type(expected)
                                 or supplied.sha256 != expected.sha256):
        raise ModelError('currentness_verification_mismatch')
    return expected


def selected_artifacts(records, artifact_ids, verification):
    """Build sort inputs only after select_query has checked the read binding."""
    ids = set(artifact_ids)
    artifacts = {record.identity.id: record.data for record in records if record.identity.id in ids}
    if verification is not None:
        for identifier, result in computed_results(verification.data).items():
            if identifier in artifacts:
                artifacts[identifier] = {**artifacts[identifier],
                    'verification_result': result}
    return artifacts
