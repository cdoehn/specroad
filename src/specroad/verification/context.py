"""Appendix L subject projection and explicit configuration-context freshness.

Inputs are owned model values. This layer neither selects authoritative runs
nor aggregates verification results, reads files or executes a test procedure.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..configurations import EffectiveConfiguration
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from ..storage.record_artifact import RecordArtifact
from ._context_subject import owned_subject as _subject
from ._subject_binding import (CONTEXT_HASH_ALGORITHM, project_subject,
                              subject_binding, subject_context_sha256)
from ._context_contract import contract_check as _contract_check


def verification_context_projection(subject):
    """Return the detached, locally validated subject projection of Appendix L.

    Calculated results and run fields are not valid stored fields of these
    three subject types. They are rejected by their native schemas, not silently
    stripped from an otherwise invalid record. A waiver is a workflow decision,
    not part of the check subject. Provenance retains source data and extensions;
    its capture timestamp is purely audit metadata.
    """
    return project_subject(_subject(subject).data)


def verification_context_sha256(subject):
    return subject_context_sha256(_subject(subject).data)


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
            'subject_binding': subject_binding(value),
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


def assess_verification_context(context, evidence, *, contract=None):
    """Compare subject freshness and exact or explicitly independent configuration.

    Evidence's old full hash and revision remain audit data. Its result and run
    state are retained but do not decide subject freshness. Independent reuse
    requires a supplied, matching, context-current contract and recorded check.
    The two-argument bound-config path retains its existing result contract.
    """
    if type(context) is not VerificationContext:
        raise ModelError('typed_verification_context_required')
    if type(evidence) is not RecordArtifact:
        raise ModelError('typed_verification_evidence_required')
    observed = RecordArtifact(evidence.source_bytes, expected_type='evidence', path=evidence.path)
    record = observed.data
    if 'configuration_hash' not in record or 'configuration_policy' not in record:
        raise ModelError('evidence_configuration_binding_required', path=evidence.path)
    if contract is None and record['configuration_policy'] != 'bound':
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
    contract_report = {}
    if contract is not None:
        contract_report, contract_reasons = _contract_check(data, record, contract)
        reasons.extend(contract_reasons)
    independent = contract_report.get('contract_configuration_independent', False)
    if not independent and record['configuration_hash'] != data['configuration_hash']:
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
        'write_authorized': False, 'approval_granted': False, **contract_report}
    result = object.__new__(VerificationContextAssessment)
    object.__setattr__(result, '_encoded', canonical_json_bytes(report))
    return result
