"""All same-product observations survive beside expected runs and later passes."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.configurations import resolve_configuration
from specroad.graph.relations import SourceRelations
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.storage.domain_artifact import DomainArtifact
from specroad.verification import (VerificationContext, VerificationContract,
    VerificationTest, VerificationEvaluation, VerificationEvaluationError,
    VerificationRunSelection, select_verification_runs)
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.records import record_value, ref
from support.targets import model
from test_verification_evaluation import descriptor
from test_verification_required_checks import edge


def case(*, policy='bound', direct=False, with_test=False, configured=True,
         subject_kind='requirement', expected=('ci:expected',)):
    subject_id = ref({'requirement': 'REQ', 'capability': 'CAP', 'task': 'TASK'}[subject_kind])
    contract_id = ref('TEST') if direct else ref('VER')
    test_id = ref('TEST') if direct or with_test else None
    records = [domain_value(subject_kind, id=subject_id, relations=[edge(contract_id, 0)])]
    if not direct:
        records.append(record_value('verification', subjects=[subject_id], configuration_policy=policy,
            evidence_slots=[{'check_id': 'overall', 'test_id': test_id, 'dimension': 'overall'}]))
    if test_id is not None:
        records.append(record_value('test'))
    configuration_id = ref('CFG') if configured else None
    if configured:
        records.append(record_value('configuration'))
    configuration = None if not configured else resolve_configuration(
        [SourceRelations(artifact_bytes(v)) for v in records], configuration_id)
    key = {'subject_artifact_id': subject_id, 'contract_id': contract_id,
           'test_id': test_id, 'check_id': 'overall'}
    evaluation = descriptor(configuration=configuration, required_runs=[{**key, 'run_ids': list(expected)}])
    return records, evaluation, configuration_id, key


def observation(records, evaluation, key, *, token='1', run='ci:observed', result='failed', **extra):
    ids = {key['subject_artifact_id'], key['contract_id'], key['test_id']} - {None}
    subjects = []
    for value in records:
        if value['id'] not in ids:
            continue
        kind = value['artifact_type']
        cls = {'capability': DomainArtifact, 'requirement': DomainArtifact,
               'task': DomainArtifact, 'verification': VerificationContract,
               'test': VerificationTest}[kind]
        subjects.append(VerificationContext(cls(artifact_bytes(value)), configuration=None).subject_binding)
    return record_value('evidence', id=ref('EVD', token), result=result, subjects=subjects,
        configuration_hash=evaluation.data['configuration_hash'], configuration_policy='bound',
        run_context={'subject_id': evaluation.data['evaluated_subject']['subject_id'],
            'subject_state_sha256': evaluation.state_sha256, 'run_id': run,
            'check_id': key['check_id'], 'test_id': key['test_id']}, **extra)


def select(records, evaluation, configuration_id):
    return select_verification_runs(model(records), evaluation, configuration_id=configuration_id)


def runs(report):
    return {item['run_id']: item for item in report['checks'][0]['runs']}


def test_observed_failure_remains_a_candidate_after_later_success_and_beside_missing_expectation():
    records, evaluation, cfg, key = case()
    failure = observation(records, evaluation, key, run='ci:failure')
    success = observation(records, evaluation, key, token='2', run='ci:success', result='passed',
                          produced_at='2026-10-21T00:00:00Z')
    supplied = model(records + [success, failure]); before = supplied.source_files
    with no_write_attempts(): result = select_verification_runs(supplied, evaluation, configuration_id=cfg)
    data = result.data; selected = runs(data)
    assert list(selected) == ['ci:expected', 'ci:failure', 'ci:success']
    assert selected['ci:expected'] == {'run_id': 'ci:expected', 'expected': True, 'evidence': []}
    assert not selected['ci:failure']['expected'] and not selected['ci:success']['expected']
    assert selected['ci:failure']['evidence'][0]['result'] == 'failed'
    assert selected['ci:success']['evidence'][0]['result'] == 'passed'
    assert data['selection_status'] == 'selected' and data['run_selection_evaluated']
    assert data['unselected_evidence_ids'] == []
    assert supplied.source_files == before and data['input_sha256'] == supplied._sources_sha256
    assert data['evaluation_sha256'] == evaluation.sha256
    assert 'verification_result' not in data
    assert all(data[flag] is False for flag in ('input_bytes_verified', 'input_roles_verified',
        'project_files_verified', 'project_required_checks_complete', 'context_freshness_evaluated',
        'run_replacements_evaluated', 'result_aggregation_evaluated', 'full_verification_evaluated',
        'external_run_verified', 'release_readiness_evaluated', 'test_code_executed',
        'write_authorized', 'approval_granted'))


def test_every_evidence_of_one_expected_run_is_retained_without_newest_success_selection():
    records, evaluation, cfg, key = case(expected=('ci:shared',))
    first = observation(records, evaluation, key, run='ci:shared')
    second = observation(records, evaluation, key, token='2', run='ci:shared', result='passed')
    data = select(records + [second, first], evaluation, cfg).data
    selected = runs(data)['ci:shared']
    assert selected['expected'] and len(runs(data)) == 1
    assert [(e['evidence_id'], e['result']) for e in selected['evidence']] == [
        (first['id'], 'failed'), (second['id'], 'passed')]
    assert [e['artifact_sha256'] for e in data['evidence_inventory']] == [
        canonical_json_sha256(first), canonical_json_sha256(second)]
    assert [e['source_sha256'] for e in data['evidence_inventory']] == [
        sha256(canonical_json_bytes(first)).hexdigest(), sha256(canonical_json_bytes(second)).hexdigest()]


def test_one_evidence_witnesses_only_its_explicitly_recorded_subjects_of_a_shared_contract():
    records, evaluation, cfg, key = case()
    another = domain_value('requirement', id=ref('REQ', '2'), relations=[edge(ref('VER'), 1)])
    records.append(another); records[1]['subjects'].append(another['id'])
    value = evaluation.data
    other_key = {**value['required_runs'][0], 'subject_artifact_id': another['id']}
    value['required_runs'].append(other_key); evaluation = VerificationEvaluation(artifact_bytes(value))
    item = observation(records, evaluation, key)
    data = select(records + [item], evaluation, cfg).data
    assert len(data['checks']) == 2
    assert len(data['checks'][0]['runs']) == 2 and len(data['checks'][1]['runs']) == 1
    item['subjects'].append(VerificationContext(DomainArtifact(artifact_bytes(another)),
                                               configuration=None).subject_binding)
    data = select(records + [item], evaluation, cfg).data
    assert [len(check['runs']) for check in data['checks']] == [2, 2]
    assert [check['runs'][1]['evidence'][0]['evidence_id'] for check in data['checks']] == [item['id']] * 2


def test_one_run_can_witness_multiple_slots_without_merging_their_evidence():
    records, evaluation, cfg, key = case(expected=('ci:shared',))
    records[1]['evidence_slots'].append({'check_id': 'second', 'test_id': None, 'dimension': 'overall'})
    value = evaluation.data; value['required_runs'].append({**value['required_runs'][0], 'check_id': 'second'})
    evaluation = VerificationEvaluation(artifact_bytes(value))
    first = observation(records, evaluation, key, run='ci:shared')
    second = observation(records, evaluation, {**key, 'check_id': 'second'}, token='2',
                         run='ci:shared', result='passed')
    data = select(records + [second, first], evaluation, cfg).data
    assert [(check['check_id'], check['runs'][0]['evidence'][0]['result']) for check in data['checks']] == [
        ('overall', 'failed'), ('second', 'passed')]
    assert all(len(check['runs']) == len(check['runs'][0]['evidence']) == 1 for check in data['checks'])


def test_independent_explicit_scope_restricts_keys_without_hiding_supplied_evidence():
    from test_verification_required_checks_right import bindings_for, scope
    records, evaluation, cfg, key = case()
    records.append(domain_value('requirement', id=ref('REQ', '2')))
    item = observation(records, evaluation, key); supplied = model(records + [item])
    data = select_verification_runs(supplied, evaluation, configuration_id=cfg,
        scope_descriptor=scope(ref(), configuration_id=cfg), scope_bindings=bindings_for(supplied)).data
    assert data['selection_status'] == 'selected' and len(data['checks']) == 1
    assert runs(data)['ci:observed']['evidence'][0]['evidence_id'] == item['id']


def test_descriptor_cached_data_cannot_replace_its_original_bound_bytes():
    records, evaluation, cfg, key = case()
    item = observation(records, evaluation, key)
    before = select(records + [item], evaluation, cfg).data
    wrong = deepcopy(evaluation.data); wrong['required_runs'][0]['run_ids'] = ['ci:invented']
    object.__setattr__(evaluation, '_encoded', canonical_json_bytes(wrong))
    assert select(records + [item], evaluation, cfg).data == before


@pytest.mark.parametrize('result', ['failed', 'passed', 'running', 'not_measured'])
def test_result_strings_are_preserved_without_a_positive_default(result):
    records, evaluation, cfg, key = case()
    item = observation(records, evaluation, key, result=result)
    data = select(records + [item], evaluation, cfg).data
    evidence = runs(data)['ci:observed']['evidence'][0]
    assert evidence['result'] == result and evidence['subjects'] == item['subjects']
    assert evidence['run_context'] == item['run_context']
    assert evidence['source_sha256'] == next(x['source_sha256'] for x in data['evidence_inventory'])
    assert not data['result_aggregation_evaluated']


@pytest.mark.parametrize('field,value', [('subject_id', 'other-product'),
    ('subject_state_sha256', 'f' * 64), ('check_id', 'different'), ('test_id', ref('TEST'))])
def test_other_product_or_slot_never_becomes_a_candidate(field, value):
    records, evaluation, cfg, key = case()
    item = observation(records, evaluation, key)
    item['run_context'][field] = value
    data = select(records + [item], evaluation, cfg).data
    assert list(runs(data)) == ['ci:expected']
    assert data['unselected_evidence_ids'] == [item['id']]
    assert data['evidence_inventory'][0]['artifact_sha256'] == canonical_json_sha256(item)


@pytest.mark.parametrize('missing', ['subject', 'contract', 'test'])
def test_complete_key_requires_each_recorded_artifact_binding(missing):
    records, evaluation, cfg, key = case(with_test=True)
    item = observation(records, evaluation, key)
    removed = {'subject': key['subject_artifact_id'], 'contract': key['contract_id'], 'test': key['test_id']}[missing]
    item['subjects'] = [s for s in item['subjects'] if s['artifact_id'] != removed]
    data = select(records + [item], evaluation, cfg).data
    assert list(runs(data)) == ['ci:expected'] and data['unselected_evidence_ids'] == [item['id']]


@pytest.mark.parametrize('contract_policy,evidence_policy,matches', [
    ('bound', 'bound', False), ('bound', 'independent', False),
    ('independent', 'bound', False), ('independent', 'independent', True)])
def test_cross_configuration_requires_explicit_independence_not_only_a_label(contract_policy, evidence_policy, matches):
    records, evaluation, cfg, key = case(policy=contract_policy)
    item = observation(records, evaluation, key)
    item.update(configuration_hash='f' * 64, configuration_policy=evidence_policy)
    data = select(records + [item], evaluation, cfg).data
    assert ('ci:observed' in runs(data)) is matches
    assert data['unselected_evidence_ids'] == ([] if matches else [item['id']])


def test_stale_independence_declaration_cannot_enable_cross_configuration_reuse():
    records, evaluation, cfg, key = case(policy='independent')
    item = observation(records, evaluation, key)
    item.update(configuration_hash='f' * 64, configuration_policy='independent')
    records[1]['oracle'] = 'Changed measurement meaning'
    data = select(records + [item], evaluation, cfg).data
    assert list(runs(data)) == ['ci:expected'] and data['unselected_evidence_ids'] == [item['id']]


def test_unconfigured_evaluation_uses_only_explicit_independent_contract_policy():
    records, evaluation, cfg, key = case(policy='independent', configured=False)
    item = observation(records, evaluation, key); item['configuration_policy'] = 'independent'
    data = select(records + [item], evaluation, cfg).data
    assert runs(data)['ci:observed']['evidence'][0]['configuration_hash'] is None


@pytest.mark.parametrize('field', ['configuration_hash', 'configuration_policy'])
def test_missing_configuration_declaration_is_not_inferred(field):
    records, evaluation, cfg, key = case(policy='independent')
    item = observation(records, evaluation, key); item['configuration_policy'] = 'independent'
    del item[field]
    data = select(records + [item], evaluation, cfg).data
    assert list(runs(data)) == ['ci:expected']


@pytest.mark.parametrize('subject_kind', ['requirement', 'capability', 'task'])
def test_direct_test_contract_keeps_all_bound_candidates_and_does_not_invent_policy(subject_kind):
    records, evaluation, cfg, key = case(direct=True, subject_kind=subject_kind)
    item = observation(records, evaluation, key)
    data = select(records + [item], evaluation, cfg).data
    assert runs(data)['ci:observed']['evidence'][0]['evidence_id'] == item['id']
    assert data['checks'][0]['contract_id'] == data['checks'][0]['test_id'] == ref('TEST')
    item.update(configuration_hash='f' * 64, configuration_policy='independent')
    assert list(runs(select(records + [item], evaluation, cfg).data)) == ['ci:expected']


def test_no_run_context_remains_visible_without_a_synthetic_run_or_success():
    records, evaluation, cfg, key = case()
    item = observation(records, evaluation, key)
    item.update(run_context=None, unbound_reason='No retained producer run')
    data = select(records + [item], evaluation, cfg).data
    assert list(runs(data)) == ['ci:expected'] and data['unselected_evidence_ids'] == [item['id']]


def test_subject_context_changes_do_not_hide_the_same_product_observation_before_freshness_stage():
    records, evaluation, cfg, key = case()
    item = observation(records, evaluation, key)
    item['subjects'][0]['verification_context_sha256'] = 'f' * 64
    data = select(records + [item], evaluation, cfg).data
    assert runs(data)['ci:observed']['evidence'][0]['subjects'] == item['subjects']
    assert not data['context_freshness_evaluated']


@pytest.mark.parametrize('field,value', [('subject_id', 'other-product'), ('subject_state_sha256', 'f' * 64)])
def test_conflicting_product_bindings_of_one_run_are_rejected_before_selection(field, value):
    records, evaluation, cfg, key = case()
    first = observation(records, evaluation, key)
    second = observation(records, evaluation, key, token='2')
    second['run_context'][field] = value
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        select(records + [first, second], evaluation, cfg)
    assert caught.value.reason == 'evidence_run_identity_conflict'


@pytest.mark.parametrize('run_id', ['bare', ':local', 'producer:', ' producer:local'])
def test_unqualified_observed_run_id_is_not_assigned_an_invented_producer(run_id):
    records, evaluation, cfg, key = case()
    item = observation(records, evaluation, key, run=run_id)
    with pytest.raises(VerificationEvaluationError) as caught:
        select(records + [item], evaluation, cfg)
    assert caught.value.reason == 'namespaced_evidence_run_id_required'
    assert caught.value.code == 'SRV175' and caught.value.pointer == '/run_context/run_id'


@pytest.mark.parametrize('change', ['none', 'configuration', 'contractless_subject'])
def test_incomplete_independent_coverage_cannot_start_run_selection(change):
    records, evaluation, cfg, key = case()
    item = observation(records, evaluation, key)
    if change == 'none': evaluation = None
    if change == 'configuration': evaluation = descriptor(required_runs=[{**key, 'run_ids': ['ci:expected']}])
    if change == 'contractless_subject': records.append(domain_value('requirement', id=ref('REQ', '2')))
    data = select(records + [item], evaluation, cfg).data
    assert data['selection_status'] == 'incomplete' and not data['run_selection_evaluated']
    assert data['checks'] == [] and data['unselected_evidence_ids'] == [item['id']]


def test_foreign_descriptor_key_is_rejected_by_the_independent_required_set():
    records, evaluation, cfg, key = case()
    value = evaluation.data; value['required_runs'][0]['check_id'] = 'fabricated'
    with pytest.raises(VerificationEvaluationError) as caught:
        select(records, VerificationEvaluation(artifact_bytes(value)), cfg)
    assert caught.value.reason == 'unexpected_evaluation_required_key'


def test_model_order_is_not_a_latest_evidence_selector_and_values_are_owned():
    records, evaluation, cfg, key = case()
    items = [observation(records, evaluation, key),
             observation(records, evaluation, key, token='2', result='passed')]
    result = select(records + items, evaluation, cfg)
    assert result.data == select(list(reversed(records + items)), evaluation, cfg).data
    before = result.data; changed = result.data; changed['checks'].clear()
    items[0]['result'] = 'passed'
    assert result.data == before and result.sha256 == canonical_json_sha256(before)
    with pytest.raises(TypeError): bool(result)
    with pytest.raises(TypeError): VerificationRunSelection()
    with pytest.raises(FrozenInstanceError): result._encoded = b'{}'


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_run_selection_has_identical_read_only_contract_in_fresh_core_and_pyz(mode, tmp_path):
    records, evaluation, cfg, key = case()
    supplied = model(records + [observation(records, evaluation, key)])
    expected = select_verification_runs(supplied, evaluation, configuration_id=cfg).data
    body = '''import json
from specroad.changes import TargetModel
from specroad.verification import VerificationEvaluation, select_verification_runs
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
'''
    body += 'config=' + repr(supplied.configuration_bytes) + '\n'
    body += 'documents=' + repr([(d.path, d.content) for d in supplied.documents]) + '\n'
    body += 'resources=' + repr([(d.path, d.content) for d in supplied.resource_files]) + '\n'
    body += 'core_key=' + repr(supplied.profile.profile_chain[0]) + '\n'
    body += 'evaluation=VerificationEvaluation(' + repr(evaluation.source_bytes) + ')\n'
    body += 'configuration_id=' + repr(cfg) + '\n'
    body += '''profile=compose_profiles([ProfileResource(raw) for path,raw in resources],core_key=core_key)
owned=TargetModel(config,ProjectReadBinding('sample','/explicit/provider',(1,2)),
 [ModelDocument(path,raw) for path,raw in documents],profile=profile,
 resource_files=[ModelDocument(path,raw) for path,raw in resources])
print(json.dumps(select_verification_runs(owned,evaluation,configuration_id=configuration_id).data))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
