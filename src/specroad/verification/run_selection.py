"""Select every supplied run candidate without interpreting its result as a pass.

Obligations are independent of the descriptor. Observed and expected runs form
a union; import time, Evidence ID and a later success never replace a failure.
Detailed freshness/disposition and result aggregation remain separate stages.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from ..storage.record_artifact import RecordArtifact
from .evaluation import VerificationEvaluation, VerificationEvaluationError
from .required_checks import assess_required_check_coverage
from .targets import resolve_verification_target
from ._run_candidates import candidate_check


@dataclass(frozen=True, init=False)
class VerificationRunSelection:
    """Owned candidate inventory, never external execution or verification success."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use select_verification_runs')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Run selection is not verification success or approval')


def select_verification_runs(model, evaluation, *, configuration_id,
                             scope_descriptor=None, scope_bindings=None):
    """Union expected runs with all matching observations in the supplied model.

    Evidence is discovered only in the owned model, never through a file path
    or descriptor selector. Scope restricts the independently required keys;
    all supplied Evidence can witness those keys. The descriptor's product
    hash is an explicit declaration, not proof of available product inputs.
    """
    from ..changes.target_model import TargetModel
    from ..changes.evidence import _run_history
    if type(model) is not TargetModel:
        raise ModelError('verification_target_model_required')
    model = model.snapshot()
    coverage = assess_required_check_coverage(model, evaluation,
        configuration_id=configuration_id, scope_descriptor=scope_descriptor,
        scope_bindings=scope_bindings)
    required = coverage.data
    evaluation = None if evaluation is None else VerificationEvaluation(evaluation.source_bytes)
    selected = None if evaluation is None else evaluation.data
    evidence = []
    for document in model.documents:
        if parse_json_object(document.content)['artifact_type'] == 'evidence':
            record = RecordArtifact(document.content, expected_type='evidence', path=document.path)
            value = record.data
            run = value['run_context']
            if run is not None:
                namespace, separator, local = run['run_id'].partition(':')
                if (not separator or not namespace.strip() or not local.strip()
                        or run['run_id'] != run['run_id'].strip()):
                    raise VerificationEvaluationError('namespaced_evidence_run_id_required',
                        path=document.path, pointer='/run_context/run_id')
            evidence.append((record, value))
    evidence.sort(key=lambda pair: pair[1]['id'].encode('utf-8'))
    history = {value['id']: value for _, value in evidence}
    for value in history.values():
        _run_history(history, value)
    inventory = [{'evidence_id': value['id'], 'source_sha256': sha256(record.source_bytes).hexdigest(),
                  'artifact_sha256': canonical_json_sha256(value)} for record, value in evidence]
    checks, used = [], set()
    eligible = required['coverage_status'] == 'ready'
    if eligible:
        expected = {(row['subject_artifact_id'], row['contract_id'], row['test_id'], row['check_id']):
                    row['run_ids'] for row in selected['required_runs']}
        contracts = {}
        for key in required['required_set']['required_checks']:
            identity = tuple(key[field] for field in
                             ('subject_artifact_id', 'contract_id', 'test_id', 'check_id'))
            pair = identity[:2]
            if pair not in contracts:
                contracts[pair] = resolve_verification_target(model, *pair).data['contract']['record']
            snapshot = canonical_json_bytes({'key': key, 'expected_run_ids': expected[identity],
                'contract': contracts[pair],
                'evaluation_binding': {field: selected[field] for field in
                                       ('evaluated_subject', 'configuration_hash')},
                'evidence': [{'record': value, 'binding': binding}
                             for (_, value), binding in zip(evidence, inventory)]})
            check, selected_ids = candidate_check(snapshot)
            checks.append(check)
            used.update(selected_ids)
    report = {'format_version': 'verification-run-selection-v1',
        'validation_scope': 'supplied_model_run_candidates',
        'project_id': model.binding.project_id, 'input_sha256': model._sources_sha256,
        'coverage': required, 'coverage_sha256': coverage.sha256,
        'evaluation_sha256': None if evaluation is None else evaluation.sha256,
        'evaluated_subject': None if selected is None else selected['evaluated_subject'],
        'evidence_inventory': inventory, 'checks': checks,
        'unselected_evidence_ids': [item['evidence_id'] for item in inventory if item['evidence_id'] not in used],
        'selection_status': 'selected' if eligible else 'incomplete',
        'run_selection_evaluated': eligible, 'input_bytes_verified': False,
        'input_roles_verified': False, 'project_files_verified': False,
        'project_required_checks_complete': False, 'context_freshness_evaluated': False,
        'run_replacements_evaluated': False, 'result_aggregation_evaluated': False,
        'full_verification_evaluated': False, 'external_run_verified': False,
        'release_readiness_evaluated': False, 'test_code_executed': False,
        'write_authorized': False, 'approval_granted': False}
    result = object.__new__(VerificationRunSelection)
    object.__setattr__(result, '_encoded', canonical_json_bytes(report))
    return result
