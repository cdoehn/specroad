"""Pure dispositions from a frozen selection and immutable document byte pairs.

Only native record/context/configuration comparisons operate on these inputs.
Scope resolution, model ownership and public report construction stay in their
adapters. No replacement or result-aggregation policy is introduced here.
"""
from ..configurations import resolve_configuration
from ..graph.relations import SourceRelations
from ..storage.domain_artifact import DomainArtifact
from ..storage.json_syntax import parse_json_object
from ..storage.record_artifact import RecordArtifact
from .context import VerificationContext, assess_verification_context
from .contracts import VerificationContract, VerificationTest
from ._subject_binding import subject_context_sha256


def selected_run_dispositions(selection_bytes, document_inputs, configuration_id):
    """Derive detached classifications without mutating the caller's snapshot."""
    selected = parse_json_object(selection_bytes)
    eligible = selected['run_selection_evaluated']
    documents = {parse_json_object(content)['id']: (path, content) for path, content in document_inputs}
    records = {key: parse_json_object(content) for key, (_, content) in documents.items()}
    inventory = {row['evidence_id']: row for row in selected['evidence_inventory']}
    evidence = {key: RecordArtifact(documents[key][1], expected_type='evidence',
                                   path=documents[key][0]) for key in inventory}
    configuration = None
    if eligible and configuration_id is not None:
        configuration = resolve_configuration(
            [SourceRelations(content, path=path) for path, content in document_inputs], configuration_id)
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
        contract = (VerificationContract(documents[key['contract_id']][1],
                        path=documents[key['contract_id']][0])
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
                            cls(document[1], path=document[0]), configuration=configuration))
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

    return checks, list(dispositions.values()), missing_runs, unresolved
