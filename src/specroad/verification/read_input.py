"""Owned, explicitly evaluated input for coverage and synchronous read adapters.

The supplied model and independent native scope define the read boundary.
No live discovery, clock, executable checkpoint or release permission is used.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from .aggregation import aggregate_verification_results
from .evaluation import VerificationEvaluation
from ._read_evaluation import computed_results, record_bindings, resolve_read_evaluation


class VerificationReadBindingConflict(ModelError):
    """A changed saved input or conflicting Release selection; no fallback."""
    exit_code = 6


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
                'evaluated_at', 'scope_descriptor', 'scope_sha256', 'configuration_hash')},
            **({} if data['release_selection'] is None else {'release_selection': data['release_selection']})}

    @property
    def work_input(self):
        """Inert bytes for the native Work input store, never stored results."""
        data = self.data
        return canonical_json_bytes({'format_version': 'verification-read-work-input-v1',
            'evaluation': data['evaluation'], 'evaluation_sha256': data['evaluation_sha256'],
            'evaluated_at': data['evaluated_at'],
            'configuration_id': data['scope_descriptor']['configuration_id'],
            'scope_descriptor': data['scope_descriptor'] if data['explicit_scope'] else None,
            'verification_input_sha256': self.sha256})

    def __bool__(self):
        raise TypeError('Verification read input is not readiness or approval')


def prepare_verification_read_input(model, evaluation, *, configuration_id, inputs,
        input_roles, evaluated_at, waiver_reviews=None, waiver_verifier=None,
        scope_descriptor=None, scope_bindings=None):
    """Compute once over an owned snapshot, independent scope and explicit inputs.

    The canonical descriptor, all observations, model sources and evaluation time
    remain bound. No absolute input filename, implicit clock or guessed build is
    used. A missing descriptor stays explicit and cannot yield evidence success.
    """
    from ..changes.target_model import TargetModel
    if type(model) is not TargetModel:
        raise ModelError('verification_target_model_required')
    model = model.snapshot()
    evaluation, release = resolve_read_evaluation(model, evaluation, scope_descriptor,
        conflict_type=VerificationReadBindingConflict)
    result = aggregate_verification_results(model, evaluation,
        configuration_id=configuration_id, inputs=inputs, input_roles=input_roles,
        evaluated_at=evaluated_at, waiver_reviews=waiver_reviews, waiver_verifier=waiver_verifier,
        scope_descriptor=scope_descriptor, scope_bindings=scope_bindings)
    aggregation = result.data
    required = aggregation['replacement_assessment']['assessment']['selection']['coverage']['required_set']
    records = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
    report = {'format_version': 'verification-read-input-v1',
        'validation_scope': ('supplied_whole_project_verification_input' if scope_descriptor is None
                             else 'supplied_scope_verification_input'),
        'explicit_scope': scope_descriptor is not None, 'release_selection': release,
        'project_id': model.binding.project_id, 'input_sha256': model._sources_sha256,
        'project_configuration_sha256': canonical_json_sha256(model.configuration.data),
        'record_bindings': record_bindings(records),
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
    if data['explicit_scope']:
        # A whole-inventory query cannot silently reuse a smaller evaluated set.
        raise ModelError('verification_query_scoped_input_unsupported')
    if query.data['evaluation'] != data['evaluation']:
        raise ModelError('verification_query_evaluation_mismatch')
    if (record_bindings(records) != data['record_bindings'] or
            canonical_json_sha256(project) != data['project_configuration_sha256']):
        raise ModelError('verification_query_sources_mismatch')
    if configuration is not None or configuration_id != data['scope_descriptor']['configuration_id']:
        raise ModelError('verification_query_configuration_mismatch')
    # SRX graph roots must remain the actual stored records. Computed graph
    # projections need their own integration; do not inject a stored status.
    if query.data['srx_filters']:
        raise ModelError('verification_query_srx_provider_required')
    return computed_results(data)


def resume_verification_read_input(model, raw, *, expected_sha256, inputs, input_roles,
        scope_bindings=None, waiver_reviews=None, waiver_verifier=None):
    """Recompute from saved semantic input under an independently trusted hash.

    The host obtains raw bytes/hash from its bound Work input store and supplies
    the original model/product inputs and native scope observations separately.
    No path is opened and no serialized aggregation, callback or success is used.
    """
    if (type(raw) is not bytes or type(expected_sha256) is not str or
            len(expected_sha256) != 64 or any(c not in '0123456789abcdef' for c in expected_sha256)):
        raise ModelError('verification_work_input_binding_required')
    if sha256(raw).hexdigest() != expected_sha256:
        raise VerificationReadBindingConflict('verification_work_input_changed')
    data = parse_json_object(raw)
    if (set(data) != {'format_version', 'evaluation', 'evaluation_sha256', 'evaluated_at',
            'configuration_id', 'scope_descriptor', 'verification_input_sha256'} or
            data['format_version'] != 'verification-read-work-input-v1' or
            canonical_json_bytes(data) != raw):
        raise ModelError('verification_work_input_invalid')
    evaluation = (None if data['evaluation'] is None else
                  VerificationEvaluation(canonical_json_bytes(data['evaluation'])))
    if data['evaluation_sha256'] != (None if evaluation is None else evaluation.sha256):
        raise VerificationReadBindingConflict('verification_work_evaluation_changed')
    from ..graph.scope_descriptors import ScopeDescriptor
    scope = None if data['scope_descriptor'] is None else ScopeDescriptor(data['scope_descriptor'])
    result = prepare_verification_read_input(model, evaluation,
        configuration_id=data['configuration_id'], inputs=inputs, input_roles=input_roles,
        evaluated_at=data['evaluated_at'], scope_descriptor=scope, scope_bindings=scope_bindings,
        waiver_reviews=waiver_reviews, waiver_verifier=waiver_verifier)
    if result.work_input != raw:
        raise VerificationReadBindingConflict('verification_work_observation_changed')
    return result
