"""Independent required checks for a supplied model and separately bound scope.

The evaluation never selects subjects, contracts or slots. No files or test code
are opened, and Evidence results are not evaluated.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..configurations import evaluate_applicability, resolve_configuration
from ..graph.references import RelationReferences
from ..graph.relation_types import relation_rules
from ..graph.relations import SourceRelations
from ..graph.scope_admission import ScopeConfigurationDependencyError
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.domain_schemas import DOMAIN_TYPES
from ..model.errors import ModelError
from ..storage.domain_artifact import DomainArtifact
from ..storage.record_artifact import RecordArtifact
from ..storage.json_syntax import parse_json_object
from .evaluation import VerificationEvaluation, VerificationEvaluationError, _key
from .targets import resolve_verification_target
from ._required_scope import resolve_required_scope


@dataclass(frozen=True, init=False)
class RequiredChecksResolution:
    """Owned required-set observation, not proof of a complete live inventory."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use resolve_required_checks')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Required checks are not verification success or approval')


def resolve_required_checks(model, *, configuration_id, scope_descriptor=None, scope_bindings=None):
    """Derive all slots independently; None explicitly selects no configuration.

    Conditional subjects without a configuration remain potential obligations,
    never exclusions. A missing contract or unresolved applicability prevents a
    complete-set claim. Plan status and waivers are later aggregation inputs.
    """
    from ..changes.target_model import TargetModel, _default_scope
    if type(model) is not TargetModel:
        raise ModelError('verification_target_model_required')
    model = model.snapshot()
    scope = ScopeDescriptor({**_default_scope(), 'configuration_id': configuration_id})
    records = tuple(SourceRelations(item.content, path=item.path) for item in model.documents)
    RelationReferences(records)
    by_id = {record.identity.id: record for record in records}
    configuration = (None if configuration_id is None else
                     resolve_configuration(records, configuration_id))
    closure = None
    included = set(by_id)
    if scope_descriptor is not None or scope_bindings is not None:
        closure = resolve_required_scope(model, records, scope_descriptor, scope_bindings, configuration_id)
        scope = closure.seeds.descriptor
        included = set(closure.artifact_ids)
    source_types = {kind for rule in relation_rules('verified_by') for kind in rule.sources}
    subjects, contracts, checks, unresolved, without_checks = [], [], [], set(), []

    def classify(record):
        decision = evaluate_applicability(record, configuration).data
        if decision['status'] == 'potentially_applicable':
            unresolved.add(record.identity.id)
        return decision

    def dependency(source_id, target_id):
        if classify(by_id[target_id])['status'] == 'excluded':
            raise ScopeConfigurationDependencyError(source_id=source_id, target_id=target_id,
                                                     configuration_id=configuration_id)

    for source in sorted(records, key=lambda item: item.identity.id.encode('utf-8')):
        if source.identity.id not in included:
            continue
        if closure is not None:
            classify(source)
        if source.identity.artifact_type not in source_types:
            continue
        artifact = DomainArtifact if source.identity.artifact_type in DOMAIN_TYPES else RecordArtifact
        artifact(source.source_bytes, path=source.path)
        decision = classify(source)
        subjects.append(decision)
        if decision['status'] == 'excluded':
            continue
        targets = sorted({edge.target for edge in source.relations if edge.type == 'verified_by'},
                         key=lambda name: name.encode('utf-8'))
        if not targets:
            without_checks.append(source.identity.id)
        for target_id in targets:
            resolution = resolve_verification_target(model, source.identity.id, target_id)
            pair = resolution.data
            dependency(source.identity.id, target_id)
            for test in pair['tests']:
                dependency(target_id, test['artifact_id'])
            checks.extend(pair['required_checks'])
            contracts.append({'subject_artifact_id': source.identity.id, 'contract_id': target_id,
                              'resolution_sha256': resolution.sha256})
    checks.sort(key=_key)
    report = {'format_version': 'verification-required-checks-v1',
        'validation_scope': ('supplied_whole_project_required_checks' if closure is None
                             else 'supplied_scope_required_checks'),
        'project_id': model.binding.project_id, 'input_sha256': model._sources_sha256,
        'scope_descriptor': scope.data, 'scope_sha256': scope.sha256,
        'configuration_hash': None if configuration is None else configuration.sha256,
        'subjects': subjects, 'contracts': contracts, 'required_checks': checks,
        'required_checks_sha256': canonical_json_sha256(checks),
        'unresolved_applicability': sorted(unresolved, key=lambda name: name.encode('utf-8')),
        'subjects_without_checks': without_checks,
        'supplied_required_checks_complete': not (unresolved or without_checks),
        'project_files_verified': False, 'project_required_checks_complete': False,
        'run_selection_evaluated': False, 'full_verification_evaluated': False,
        'external_run_verified': False, 'release_readiness_evaluated': False,
        'test_code_executed': False, 'write_authorized': False, 'approval_granted': False}
    if closure is not None:
        report.update(scope_resolution=closure.data,
                      scope_resolution_sha256=closure.observation_sha256,
                      scope_providers_authenticated=False)
    result = object.__new__(RequiredChecksResolution)
    object.__setattr__(result, '_encoded', canonical_json_bytes(report))
    return result


@dataclass(frozen=True, init=False)
class RequiredCheckAssessment:
    """Required-key coverage only; product-input and run gates remain separate."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use assess_required_check_coverage')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Required-key coverage is not verification success or approval')


class RequiredCheckCoverageError(VerificationEvaluationError):
    """An invalid selection with both missing and foreign keys, bound to its scope."""

    def __init__(self, *, missing_checks, unexpected_keys, required_set_sha256, pointer):
        super().__init__('unexpected_evaluation_required_key', pointer=pointer)
        self._details = canonical_json_bytes({'missing_checks': missing_checks,
            'unexpected_keys': unexpected_keys, 'required_set_sha256': required_set_sha256})

    @property
    def details(self):
        return parse_json_object(self._details)

    def diagnostic(self):
        return {**super().diagnostic(), **self.details}


def assess_required_check_coverage(model, evaluation, *, configuration_id,
                                  scope_descriptor=None, scope_bindings=None):
    """Compare a descriptor only after independently deriving model obligations.

    Extra keys are invalid descriptors (SRV175). Missing keys or unavailable
    bindings are incomplete (SRV176). Ready means exact key/configuration
    coverage only: it neither verifies product inputs nor evaluates any run.
    """
    resolution = resolve_required_checks(model, configuration_id=configuration_id,
        scope_descriptor=scope_descriptor, scope_bindings=scope_bindings)
    required = resolution.data
    if evaluation is not None:
        if type(evaluation) is not VerificationEvaluation:
            raise VerificationEvaluationError('typed_verification_evaluation_required')
        evaluation = VerificationEvaluation(evaluation.source_bytes)
    data = None if evaluation is None else evaluation.data
    expected = {_key(row): row for row in required['required_checks']}
    selected = {} if data is None else {_key(row): row for row in data['required_runs']}
    missing = [expected[key] for key in sorted(expected.keys() - selected.keys())]
    extra = [index for index, row in enumerate([] if data is None else data['required_runs'])
             if _key(row) not in expected]
    if extra:
        unexpected = [{field: data['required_runs'][index][field] for field in
                       ('subject_artifact_id', 'contract_id', 'test_id', 'check_id')}
                      for index in extra]
        raise RequiredCheckCoverageError(missing_checks=missing, unexpected_keys=unexpected,
            required_set_sha256=resolution.sha256, pointer=f'/required_runs/{extra[0]}')
    reasons = []
    if data is None:
        reasons.append('evaluation_required')
    elif data['configuration_hash'] != required['configuration_hash']:
        reasons.append('evaluation_configuration_mismatch')
    if missing:
        reasons.append('required_check_missing')
    if required['subjects_without_checks']:
        reasons.append('verification_contract_missing')
    if required['unresolved_applicability']:
        reasons.append('verification_applicability_unresolved')
    report = {'format_version': 'verification-required-check-coverage-v1',
        'required_set': required, 'required_set_sha256': resolution.sha256,
        'evaluation_sha256': None if evaluation is None else evaluation.sha256,
        'missing_checks': missing, 'unexpected_keys': [],
        'required_keys_match': data is not None and not missing,
        'coverage_status': 'incomplete' if reasons else 'ready',
        'verification_result': 'incomplete' if reasons else None,
        'reasons': reasons,
        'diagnostics': [{'code': 'SRV176', 'severity': 'warning', 'reason': reason}
                        for reason in reasons],
        'input_bytes_verified': False, 'input_roles_checked': False,
        'project_required_checks_complete': False, 'run_selection_evaluated': False,
        'full_verification_evaluated': False, 'external_run_verified': False,
        'release_readiness_evaluated': False, 'test_code_executed': False,
        'write_authorized': False, 'approval_granted': False}
    result = object.__new__(RequiredCheckAssessment)
    object.__setattr__(result, '_encoded', canonical_json_bytes(report))
    return result
