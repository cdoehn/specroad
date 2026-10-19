"""Appendix L subject projection and bound-config Evidence freshness only.

Inputs are owned model values. This layer neither selects authoritative runs
nor aggregates verification results, reads files or executes a test procedure.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..configurations import EffectiveConfiguration
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.domain_artifact import DomainArtifact
from ..storage.json_syntax import parse_json_object
from ..storage.record_artifact import RecordArtifact
from .contracts import VerificationContract, VerificationTest

CONTEXT_HASH_ALGORITHM = 'verification_context_hash-v1'
# Only these top-level fields are removed. Names inside semantic extensions,
# oracles and structured requirement data keep their original meaning.
_EXCLUDED = frozenset({'revision', 'created_at', 'created_by', 'updated_at',
    'updated_by', 'maturity', 'implementation_status', 'verification_plan_status',
    'verification_waiver', 'relations', 'tags'})


def _subject(subject):
    if type(subject) is DomainArtifact:
        return DomainArtifact(subject.source_bytes, expected_type='requirement', path=subject.path)
    if type(subject) is VerificationContract:
        return VerificationContract(subject.source_bytes, path=subject.path)
    if type(subject) is VerificationTest:
        return VerificationTest(subject.source_bytes, path=subject.path)
    raise ModelError('typed_verification_subject_required')


def verification_context_projection(subject):
    """Return the detached, locally validated subject projection of Appendix L.

    Calculated results and run fields are not valid stored fields of these
    three subject types. They are rejected by their native schemas, not silently
    stripped from an otherwise invalid record. A waiver is a workflow decision,
    not part of the check subject. Provenance retains source data and extensions;
    its capture timestamp is purely audit metadata.
    """
    value = _subject(subject).data
    projected = {key: item for key, item in value.items() if key not in _EXCLUDED}
    if 'provenance' in value:
        projected['provenance'] = [{key: item for key, item in source.items()
                                    if key != 'captured_at'} for source in value['provenance']]
    return projected


def verification_context_sha256(subject):
    return canonical_json_sha256(verification_context_projection(subject))


@dataclass(frozen=True, init=False)
class VerificationContext:
    """One subject snapshot and explicitly supplied effective configuration.

    configuration=None explicitly denotes an unconfigured evaluation. Hashes
    for configured evaluations use the existing effective-chain manifest.
    This does not establish applicability or membership in any project scope.
    """
    _encoded: bytes

    def __init__(self, subject, *, configuration):
        owned = _subject(subject)
        value = owned.data
        if configuration is not None and type(configuration) is not EffectiveConfiguration:
            raise ModelError('typed_verification_configuration_required')
        data = {'format_version': 'verification-context-v1',
            'hash_algorithm': CONTEXT_HASH_ALGORITHM,
            'subject': value,
            'subject_source_sha256': sha256(owned.source_bytes).hexdigest(),
            'subject_binding': {'artifact_id': value['id'], 'revision': value['revision'],
                'artifact_sha256': canonical_json_sha256(value),
                'verification_context_sha256': verification_context_sha256(owned)},
            'configuration_hash': None if configuration is None else configuration.sha256}
        object.__setattr__(self, '_encoded', canonical_json_bytes(data))

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def context_sha256(self):
        return self.data['subject_binding']['verification_context_sha256']

    @property
    def subject_binding(self):
        return self.data['subject_binding']

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('A context binding is not verification success or approval')


@dataclass(frozen=True, init=False)
class VerificationContextAssessment:
    """Freshness for one subject/Evidence pair, never a verification result."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use assess_verification_context')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Context freshness is not verification success or approval')


def assess_verification_context(context, evidence):
    """Compare a recorded subject binding and an exact bound configuration.

    Evidence's old full hash and revision remain audit data. Its result and run
    context are retained but do not decide freshness. Independent reuse needs
    the separately implemented contract gate; a label cannot waive this check.
    """
    if type(context) is not VerificationContext:
        raise ModelError('typed_verification_context_required')
    if type(evidence) is not RecordArtifact:
        raise ModelError('typed_verification_evidence_required')
    observed = RecordArtifact(evidence.source_bytes, expected_type='evidence', path=evidence.path)
    record = observed.data
    if 'configuration_hash' not in record or 'configuration_policy' not in record:
        raise ModelError('evidence_configuration_binding_required', path=evidence.path)
    if record['configuration_policy'] != 'bound':
        raise ModelError('independent_verification_context_not_supported', path=evidence.path)
    data = context.data
    current = data['subject_binding']
    subjects = record['subjects']  # Native RecordArtifact validation rejects duplicate IDs.
    recorded = next((item for item in subjects if item['artifact_id'] == current['artifact_id']), None)
    reasons = []
    if recorded is None:
        reasons.append('subject_not_recorded')
    elif recorded['verification_context_sha256'] != current['verification_context_sha256']:
        reasons.append('subject_context_changed')
    if record['configuration_hash'] != data['configuration_hash']:
        reasons.append('configuration_changed')
    report = {'format_version': 'verification-context-assessment-v1',
        'hash_algorithm': CONTEXT_HASH_ALGORITHM, 'context_binding_sha256': context.sha256,
        'subject': current, 'recorded_subject': recorded, 'evidence_id': record['id'],
        'evidence_source_sha256': sha256(observed.source_bytes).hexdigest(),
        'evidence_sha256': canonical_json_sha256(record),
        'configuration_hash': data['configuration_hash'],
        'evidence_configuration_hash': record['configuration_hash'],
        'evidence_result': record['result'], 'run_context': record['run_context'],
        'freshness': 'stale' if reasons else 'current', 'context_current': not reasons,
        'reasons': reasons, 'full_verification_evaluated': False,
        'configuration_applicability_evaluated': False, 'run_selection_evaluated': False,
        'release_readiness_evaluated': False, 'test_code_executed': False,
        'write_authorized': False, 'approval_granted': False}
    result = object.__new__(VerificationContextAssessment)
    object.__setattr__(result, '_encoded', canonical_json_bytes(report))
    return result
