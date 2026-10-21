"""Explain run candidates and their context freshness without aggregating results.

Historical and unbound records remain visible. Only complete key/product/config
matches belong to a run; an absent expected observation is missing, not stale.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..configurations import resolve_configuration
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.domain_artifact import DomainArtifact
from ..storage.json_syntax import parse_json_object
from ..storage.record_artifact import RecordArtifact
from .context import VerificationContext, assess_verification_context
from .contracts import VerificationContract, VerificationTest
from .run_selection import select_verification_runs
from ._subject_binding import subject_context_sha256


@dataclass(frozen=True, init=False)
class VerificationRunAssessment:
    """Owned disposition report; neither a result aggregate nor an approval."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use assess_verification_runs')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Run dispositions are not verification success or approval')


def assess_verification_runs(model, evaluation, *, configuration_id,
                             scope_descriptor=None, scope_bindings=None):
    """Assess the native selection against original model and descriptor bytes.

    The native Appendix L projection covers Requirements, Verification and Test
    records. Other subject types retain candidates with unresolved freshness;
    their context hash is not guessed from an audit hash or a new projection.
    Input bytes/roles, replacement decisions and final results are separate gates.
    """
    from ..changes.target_model import TargetModel
    if type(model) is not TargetModel:
        raise ModelError('verification_target_model_required')
    model = model.snapshot()
    selection = select_verification_runs(model, evaluation, configuration_id=configuration_id,
        scope_descriptor=scope_descriptor, scope_bindings=scope_bindings)
    selected = selection.data
    eligible = selected['run_selection_evaluated']
    documents = {parse_json_object(d.content)['id']: d for d in model.documents}
    records = {key: parse_json_object(d.content) for key, d in documents.items()}
    inventory = {row['evidence_id']: row for row in selected['evidence_inventory']}
    evidence = {key: RecordArtifact(documents[key].content, expected_type='evidence',
                                   path=documents[key].path) for key in inventory}
    configuration = None
    if eligible and configuration_id is not None:
        configuration = resolve_configuration(
            [SourceRelations(d.content, path=d.path) for d in model.documents], configuration_id)
    dispositions = {}
    for evidence_id, binding in inventory.items():
        value = records[evidence_id]
        run = value['run_context']
        reasons = []
        if run is None:
            category = 'unbound'
            reasons.append('run_context_missing')
        elif selected['evaluated_subject'] is not None and (
                run['subject_id'] != selected['evaluated_subject']['subject_id'] or
                run['subject_state_sha256'] != selected['evaluated_subject']['state_sha256']):
            category = 'historical_other_state'
            reasons.append('evaluated_subject_mismatch')
        else:
            category = 'unselected' if eligible else 'not_evaluated'
        dispositions[evidence_id] = {**binding, 'disposition': category, 'reasons': reasons,
            'run_context': run, 'unbound_reason': value.get('unbound_reason'),
            'result': value['result'], 'candidate_checks': []}

    checks, missing_runs, unresolved = [], [], False
    context_cache = {}
    for check in selected['checks']:
        key = {field: check[field] for field in
               ('subject_artifact_id', 'contract_id', 'test_id', 'check_id')}
        ids = {key['subject_artifact_id'], key['contract_id'], key['test_id']} - {None}
        contract_value = records[key['contract_id']]
        contract = (VerificationContract(documents[key['contract_id']].content,
                        path=documents[key['contract_id']].path)
                    if contract_value['artifact_type'] == 'verification' else None)
        runs, used = [], set()
        for run in check['runs']:
            observations = []
            for observation in run['evidence']:
                evidence_id = observation['evidence_id']
                contexts, unsupported = [], []
                for subject_id in sorted(ids, key=lambda item: item.encode('utf-8')):
                    if subject_id not in context_cache:
                        document = documents[subject_id]
                        cls = {'requirement': DomainArtifact, 'verification': VerificationContract,
                               'test': VerificationTest}.get(records[subject_id]['artifact_type'])
                        context_cache[subject_id] = (None if cls is None else VerificationContext(
                            cls(document.content, path=document.path), configuration=configuration))
                    context = context_cache[subject_id]
                    if context is None:
                        unsupported.append(subject_id)
                    else:
                        contexts.append(assess_verification_context(context, evidence[evidence_id],
                                                                   contract=contract).data)
                stale = any(row['freshness'] == 'stale' for row in contexts)
                # Incomplete context coverage must never be presented as current,
                # even when all assessable contexts match.
                freshness = 'stale' if stale else ('incomplete' if unsupported else 'current')
                unresolved = unresolved or bool(unsupported)
                observations.append({**observation, 'freshness': freshness,
                    'context_assessments': contexts, 'unsupported_subject_ids': unsupported,
                    'reasons': ['subject_context_unsupported'] if unsupported else []})
                dispositions[evidence_id]['disposition'] = 'candidate'
                dispositions[evidence_id]['candidate_checks'].append({**key, 'freshness': freshness})
                used.add(evidence_id)
            if not observations:
                missing_runs.append({**key, 'run_id': run['run_id']})
            runs.append({**run, 'evidence': observations,
                'presence': 'present' if observations else 'missing',
                'current_evidence_ids': [o['evidence_id'] for o in observations if o['freshness'] == 'current'],
                'stale_evidence_ids': [o['evidence_id'] for o in observations if o['freshness'] == 'stale'],
                'unresolved_evidence_ids': [o['evidence_id'] for o in observations if o['unsupported_subject_ids']]})
        excluded = []
        for evidence_id, binding in inventory.items():
            if evidence_id in used:
                continue
            disposition = dispositions[evidence_id]
            value = records[evidence_id]
            run = value['run_context']
            reasons = list(disposition['reasons'])
            missing_subjects = []
            if run is not None and disposition['disposition'] not in ('historical_other_state', 'unbound'):
                if run['check_id'] != key['check_id']:
                    reasons.append('check_id_mismatch')
                if run['test_id'] != key['test_id']:
                    reasons.append('test_id_mismatch')
                subjects = {s['artifact_id']: s for s in value['subjects']}
                missing_subjects = sorted(ids - subjects.keys(), key=lambda item: item.encode('utf-8'))
                if missing_subjects:
                    reasons.append('subject_binding_missing')
                if 'configuration_hash' not in value or 'configuration_policy' not in value:
                    reasons.append('configuration_binding_missing')
                elif value['configuration_policy'] == 'bound':
                    if value['configuration_hash'] != selected['coverage']['required_set']['configuration_hash']:
                        reasons.append('configuration_mismatch')
                elif contract_value.get('configuration_policy') != 'independent':
                    reasons.append('independent_contract_required')
                elif (value['configuration_hash'] != selected['coverage']['required_set']['configuration_hash']
                      and key['contract_id'] in subjects
                      and subjects[key['contract_id']]['verification_context_sha256']
                          != subject_context_sha256(contract_value)):
                    reasons.append('contract_context_changed')
            excluded.append({**binding, 'disposition': (disposition['disposition']
                if disposition['disposition'] in ('historical_other_state', 'unbound') else 'unselected'),
                'reasons': reasons, 'missing_subject_ids': missing_subjects})
        checks.append({**check, 'runs': runs, 'excluded_evidence': excluded})

    report = {'format_version': 'verification-run-assessment-v1',
        'validation_scope': 'supplied_model_run_dispositions',
        'selection_sha256': selection.sha256, 'selection': selected,
        'project_id': selected['project_id'], 'input_sha256': selected['input_sha256'],
        'evaluation_sha256': selected['evaluation_sha256'],
        'checks': checks, 'evidence_dispositions': list(dispositions.values()),
        'missing_runs': missing_runs,
        'diagnostics': [{'code': 'SRV176', 'severity': 'warning',
                         'reason': 'required_run_missing', **row} for row in missing_runs],
        'assessment_status': 'assessed' if eligible else 'incomplete',
        'run_selection_evaluated': eligible, 'context_freshness_evaluated': eligible and not unresolved,
        'input_bytes_verified': False, 'input_roles_verified': False, 'project_files_verified': False,
        'project_required_checks_complete': False, 'run_replacements_evaluated': False,
        'result_aggregation_evaluated': False, 'full_verification_evaluated': False,
        'external_run_verified': False, 'release_readiness_evaluated': False,
        'test_code_executed': False, 'write_authorized': False, 'approval_granted': False}
    result = object.__new__(VerificationRunAssessment)
    object.__setattr__(result, '_encoded', canonical_json_bytes(report))
    return result
