"""Owned, explicitly evaluated input for coverage and synchronous read adapters.

This first read profile covers the supplied whole project. It performs no live
discovery, release-policy resolution or durable Work continuation.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from .aggregation import aggregate_verification_results
from .evaluation import VerificationEvaluation, VerificationEvaluationError


def _record_bindings(records):
    if type(records) not in (tuple, list) or any(type(r) is not SourceRelations for r in records):
        raise ModelError('verification_query_sources_required')
    rows = [{'id': r.identity.id, 'sha256': sha256(r.source_bytes).hexdigest()} for r in records]
    return sorted(rows, key=lambda row: row['id'].encode('utf-8'))


@dataclass(frozen=True, init=False)
class VerificationReadInput:
    """A computed observation, never a callback, live capability or approval."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use prepare_verification_read_input')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    @property
    def summary(self):
        data = self.data
        return {'verification_input_sha256': self.sha256,
            **{key: data[key] for key in ('evaluation_sha256', 'aggregation_sha256',
                'evaluated_at', 'scope_descriptor', 'scope_sha256', 'configuration_hash')}}

    def __bool__(self):
        raise TypeError('Verification read input is not readiness or approval')


def prepare_verification_read_input(model, evaluation, *, configuration_id, inputs,
        input_roles, evaluated_at, waiver_reviews=None, waiver_verifier=None):
    """Compute once over an owned whole-project snapshot and explicit test inputs.

    The canonical descriptor, all observations, model sources and evaluation time
    remain bound. No absolute input filename, implicit clock or guessed build is
    used. A missing descriptor stays explicit and cannot yield evidence success.
    """
    from ..changes.target_model import TargetModel
    if type(model) is not TargetModel:
        raise ModelError('verification_target_model_required')
    model = model.snapshot()
    if evaluation is not None:
        if type(evaluation) is not VerificationEvaluation:
            raise VerificationEvaluationError('typed_verification_evaluation_required')
        evaluation = VerificationEvaluation(evaluation.source_bytes)
    result = aggregate_verification_results(model, evaluation,
        configuration_id=configuration_id, inputs=inputs, input_roles=input_roles,
        evaluated_at=evaluated_at, waiver_reviews=waiver_reviews, waiver_verifier=waiver_verifier)
    aggregation = result.data
    required = aggregation['replacement_assessment']['assessment']['selection']['coverage']['required_set']
    records = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
    report = {'format_version': 'verification-read-input-v1',
        'validation_scope': 'supplied_whole_project_verification_input',
        'project_id': model.binding.project_id, 'input_sha256': model._sources_sha256,
        'project_configuration_sha256': canonical_json_sha256(model.configuration.data),
        'record_bindings': _record_bindings(records),
        'evaluation': None if evaluation is None else evaluation.data,
        'evaluation_sha256': aggregation['evaluation_sha256'], 'evaluated_at': evaluated_at,
        'scope_descriptor': required['scope_descriptor'], 'scope_sha256': required['scope_sha256'],
        'configuration_hash': required['configuration_hash'],
        'aggregation': aggregation, 'aggregation_sha256': result.sha256,
        'project_files_verified': False, 'evaluation_identity_history_checked': False,
        'external_run_verified': False, 'release_readiness_evaluated': False,
        'write_authorized': False, 'approval_granted': False}
    value = object.__new__(VerificationReadInput)
    object.__setattr__(value, '_encoded', canonical_json_bytes(report))
    return value


def checked_model_input(model, value):
    """Bind a view or coverage consumer to the exact original model snapshot."""
    if type(value) is not VerificationReadInput:
        raise ModelError('typed_verification_read_input_required')
    from ..changes.target_model import TargetModel
    if type(model) is not TargetModel:
        raise ModelError('verification_target_model_required')
    model = model.snapshot()
    data = value.data
    if model.binding.project_id != data['project_id'] or model._sources_sha256 != data['input_sha256']:
        raise ModelError('verification_read_input_model_mismatch')
    return model, data


def checked_query_input(value, records, query, project, configuration, configuration_id):
    """Read-only record consumers must declare the same descriptor and context."""
    if type(value) is not VerificationReadInput:
        raise ModelError('typed_verification_read_input_required')
    data = value.data
    if query.data['evaluation'] != data['evaluation']:
        raise ModelError('verification_query_evaluation_mismatch')
    if (_record_bindings(records) != data['record_bindings'] or
            canonical_json_sha256(project) != data['project_configuration_sha256']):
        raise ModelError('verification_query_sources_mismatch')
    if configuration is not None or configuration_id != data['scope_descriptor']['configuration_id']:
        raise ModelError('verification_query_configuration_mismatch')
    # SRX graph roots must remain the actual stored records. Computed graph
    # projections need their own integration; do not inject a stored status.
    if query.data['srx_filters']:
        raise ModelError('verification_query_srx_provider_required')
    return {row['subject_artifact_id']: row['verification_result']
            for row in data['aggregation']['subjects']}
