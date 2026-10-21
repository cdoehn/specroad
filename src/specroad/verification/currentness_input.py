"""Explicit shared observations for read consumers, never live approval.

The host supplies the complete native code observations and one independently
evaluated verification input. Stored status fields, dicts and callbacks cannot
replace either. Reuse binds the original model bytes, not present disk currency.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..graph.relations import SourceRelations
from ..graph.review_status import RelationReviewStatuses
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.configuration import ProjectConfiguration
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from .code_reference_state import CodeReferenceState
from .coverage import assess_verification_coverage
from .read_input import checked_model_input
from ._read_evaluation import record_bindings


@dataclass(frozen=True, init=False)
class CurrentnessReadInput:
    """Owned evidence/code/review observations; no IO, clock or write permit."""
    _encoded: bytes
    _verification: object

    def __init__(self, *args, **kwargs):
        raise TypeError('Use prepare_currentness_read_input')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    @property
    def observation(self):
        return {'sha256': self.sha256, 'observation': self.data}

    @property
    def verification(self):
        """The same native input for existing computed query/filter adapters."""
        return self._verification

    def __bool__(self):
        raise TypeError('Currentness observations are not readiness or approval')


def prepare_currentness_read_input(model, verification, *, code_states=()):
    """Combine complete native observations for an explicitly supplied model.

    A missing code file is a native H.3 ``missing`` observation, not an omitted
    code_ref. All code references must occur exactly once. The whole-inventory
    adapters do not accept a partial verification scope. No serialized results
    are deserialized into native capabilities and no record is updated.
    """
    model, bound = checked_model_input(model, verification)
    if bound['explicit_scope']:
        raise ModelError('currentness_whole_project_input_required')
    if type(code_states) not in (tuple, list) or any(type(v) is not CodeReferenceState for v in code_states):
        raise ModelError('currentness_native_code_states_required')
    records = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
    expected = {r.identity.id: sha256(r.source_bytes).hexdigest() for r in records
                if r.identity.artifact_type == 'code_ref'}
    codes = {}
    for value in code_states:
        data = value.data
        identity = data['reference']['id']
        if identity in codes or expected.get(identity) != data['reference_sha256']:
            raise ModelError('currentness_code_binding_mismatch')
        codes[identity] = {'artifact_id': identity, 'assessment_sha256': value.sha256, **data}
    if set(codes) != set(expected):
        raise ModelError('currentness_code_inventory_incomplete')
    reviews = RelationReviewStatuses(records).data
    review_groups = {state: {
        'relation_ids': sorted(r['relation_id'] for r in reviews['relations'] if r['status'] == state),
        'affected_ids': sorted({r[k] for r in reviews['relations'] if r['status'] == state
                                for k in ('source_id', 'target_id')})}
        for state in ('current', 'unreviewed', 'suspect', 'invalid')}
    coverage = assess_verification_coverage(model, verification)
    data = {'format_version': 'currentness-read-input-v1',
        'validation_scope': 'supplied_model_and_native_observations',
        'project_id': bound['project_id'], 'input_sha256': bound['input_sha256'],
        'project_configuration_sha256': bound['project_configuration_sha256'],
        'record_bindings': bound['record_bindings'],
        'verification_summary': verification.summary, 'coverage': coverage.data,
        'coverage_sha256': coverage.sha256,
        'code_states': [codes[key] for key in sorted(codes)],
        'relation_reviews': reviews, 'review_groups': review_groups,
        'project_files_verified': False, 'atomic_snapshot': False,
        'external_run_verified': False, 'release_readiness_evaluated': False,
        'source_code_executed': False, 'write_authorized': False, 'approval_granted': False}
    value = object.__new__(CurrentnessReadInput)
    object.__setattr__(value, '_encoded', canonical_json_bytes(data))
    object.__setattr__(value, '_verification', verification)
    return value


def checked_currentness_model(model, value, *, verification=None):
    if type(value) is not CurrentnessReadInput:
        raise ModelError('typed_currentness_read_input_required')
    model, _ = checked_model_input(model, value._verification)
    if verification is not None and (type(verification) is not type(value._verification)
                                    or verification.sha256 != value._verification.sha256):
        raise ModelError('currentness_verification_mismatch')
    return model, value.observation


def checked_currentness_records(value, records, configuration, configuration_id=None):
    """Bind record adapters to the full supplied inventory and exact selection."""
    if type(value) is not CurrentnessReadInput:
        raise ModelError('typed_currentness_read_input_required')
    if type(configuration) is not ProjectConfiguration:
        raise ModelError('currentness_project_configuration_required')
    data = value.data
    if (configuration.project_id != data['project_id'] or
            canonical_json_sha256(configuration.data) != data['project_configuration_sha256'] or
            record_bindings(records) != data['record_bindings']):
        raise ModelError('currentness_sources_mismatch')
    if configuration_id != data['verification_summary']['scope_descriptor']['configuration_id']:
        raise ModelError('currentness_configuration_mismatch')
    return value.observation
