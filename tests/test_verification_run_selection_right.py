"""Run provenance, absence and semantic freshness cannot imply a passed result."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.verification import (VerificationEvaluation, VerificationEvaluationError,
    VerificationRunAssessment, assess_verification_runs, select_verification_runs)
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.records import ref
from support.targets import model
from test_verification_run_selection import case, observation, runs
from test_verification_required_checks import edge
from test_verification_required_checks_right import bindings_for, scope


def assess(records, evaluation, cfg):
    return assess_verification_runs(model(records), evaluation, configuration_id=cfg)


def dispositions(report):
    return {row['evidence_id']: row for row in report['evidence_dispositions']}


def observed(report, run='ci:observed'):
    return runs(report)[run]['evidence'][0]


def test_historical_unbound_stale_and_missing_are_separate_without_any_success_claim():
    records, evaluation, cfg, key = case()
    current = observation(records, evaluation, key)
    stale = observation(records, evaluation, key, token='2', run='ci:stale')
    stale['subjects'][0]['verification_context_sha256'] = 'f' * 64
    historical = observation(records, evaluation, key, token='3', run='ci:old')
    historical['run_context']['subject_state_sha256'] = 'e' * 64
    unbound = observation(records, evaluation, key, token='4')
    unbound.update(run_context=None, unbound_reason='Producer did not retain run provenance')
    supplied = model(records + [unbound, current, historical, stale]); before = supplied.source_files
    with no_write_attempts():
        value = assess_verification_runs(supplied, evaluation, configuration_id=cfg)
    data = value.data; selected = runs(data); states = dispositions(data)
    assert states[historical['id']]['disposition'] == 'historical_other_state'
    assert states[unbound['id']]['disposition'] == 'unbound'
    assert states[unbound['id']]['unbound_reason'] == unbound['unbound_reason']
    assert states[current['id']]['disposition'] == states[stale['id']]['disposition'] == 'candidate'
    assert observed(data)['freshness'] == 'current' and observed(data)['result'] == 'failed'
    assert observed(data, 'ci:stale')['freshness'] == 'stale'
    assert selected['ci:expected']['presence'] == 'missing' and selected['ci:expected']['evidence'] == []
    assert data['missing_runs'] == [{**key, 'run_id': 'ci:expected'}]
    assert data['diagnostics'] == [{'code': 'SRV176', 'severity': 'warning',
        'reason': 'required_run_missing', **key, 'run_id': 'ci:expected'}]
    assert list(selected) == ['ci:expected', 'ci:observed', 'ci:stale']
    assert data['selection'] == select_verification_runs(supplied, evaluation, configuration_id=cfg).data
    assert data['selection_sha256'] == canonical_json_sha256(data['selection'])
    assert data['context_freshness_evaluated'] and data['assessment_status'] == 'assessed'
    assert 'verification_result' not in data and supplied.source_files == before
    assert not any(data[f] for f in ('input_bytes_verified', 'input_roles_verified',
        'project_files_verified', 'project_required_checks_complete', 'run_replacements_evaluated',
        'result_aggregation_evaluated', 'full_verification_evaluated', 'external_run_verified',
        'release_readiness_evaluated', 'test_code_executed', 'write_authorized', 'approval_granted'))


@pytest.mark.parametrize('part,field,value', [
    (0, 'statement', 'A changed requirement'), (0, 'owner', 'different-owner'),
    (1, 'oracle', 'A changed oracle'), (1, 'procedure', ['A changed procedure']),
    (2, 'oracle', 'A changed test oracle'), (2, 'test_type', 'performance')])
def test_every_required_subject_contract_and_test_context_is_checked(part, field, value):
    records, evaluation, cfg, key = case(with_test=True, expected=('ci:observed',))
    item = observation(records, evaluation, key)
    records[part][field] = value
    data = assess(records + [item], evaluation, cfg).data
    candidate = observed(data)
    assert candidate['freshness'] == 'stale' and data['missing_runs'] == []
    assert runs(data)['ci:observed']['presence'] == 'present'
    assert runs(data)['ci:observed']['stale_evidence_ids'] == [item['id']]
    assert runs(data)['ci:observed']['current_evidence_ids'] == []
    changed = [c for c in candidate['context_assessments']
               if c['subject']['artifact_id'] == records[part]['id']][0]
    assert changed['freshness'] == 'stale' and 'subject_context_changed' in changed['reasons']


@pytest.mark.parametrize('part', [0, 1, 2])
@pytest.mark.parametrize('field,value', [('revision', 7), ('maturity', 'proposed'),
    ('tags', ['reviewed']), ('updated_at', '2026-10-21T01:00:00Z')])
def test_audit_and_workflow_changes_do_not_stale_a_matching_observation(part, field, value):
    records, evaluation, cfg, key = case(with_test=True)
    item = observation(records, evaluation, key)
    records[part][field] = value
    candidate = observed(assess(records + [item], evaluation, cfg).data)
    assert candidate['freshness'] == 'current'
    changed = next(c for c in candidate['context_assessments']
                   if c['subject']['artifact_id'] == records[part]['id'])
    assert changed['subject']['artifact_sha256'] != changed['recorded_subject']['artifact_sha256']
    assert changed['subject']['verification_context_sha256'] == changed['recorded_subject']['verification_context_sha256']


def test_current_and_stale_evidence_of_one_run_both_remain_visible():
    records, evaluation, cfg, key = case(expected=('ci:observed',))
    stale = observation(records, evaluation, key, result='passed')
    stale['subjects'][0]['verification_context_sha256'] = 'f' * 64
    current = observation(records, evaluation, key, token='2', result='failed')
    data = assess(records + [current, stale], evaluation, cfg).data
    run = runs(data)['ci:observed']
    assert run['presence'] == 'present' and data['missing_runs'] == []
    assert run['stale_evidence_ids'] == [stale['id']] and run['current_evidence_ids'] == [current['id']]
    assert [(e['result'], e['freshness']) for e in run['evidence']] == [('passed', 'stale'), ('failed', 'current')]
    assert not data['result_aggregation_evaluated']


@pytest.mark.parametrize('field,value', [('subject_id', 'another-product'),
    ('subject_state_sha256', 'e' * 64)])
def test_other_product_binding_is_historical_even_when_expected_run_id_matches(field, value):
    records, evaluation, cfg, key = case(expected=('ci:observed',))
    item = observation(records, evaluation, key); item['run_context'][field] = value
    data = assess(records + [item], evaluation, cfg).data
    assert dispositions(data)[item['id']]['disposition'] == 'historical_other_state'
    assert observed_history(data, item_id=item['id']) == 'historical_other_state'
    assert runs(data)['ci:observed']['presence'] == 'missing'
    assert data['missing_runs'] == [{**key, 'run_id': 'ci:observed'}]


def observed_history(data, *, item_id):
    return next(row['disposition'] for row in data['checks'][0]['excluded_evidence']
                if row['evidence_id'] == item_id)


def test_no_evidence_means_all_expected_runs_missing_without_stale_or_current_observations():
    records, evaluation, cfg, key = case(expected=('ci:one', 'ci:two'))
    data = assess(records, evaluation, cfg).data
    assert data['evidence_dispositions'] == []
    assert data['missing_runs'] == [{**key, 'run_id': name} for name in ('ci:one', 'ci:two')]
    assert all(r['presence'] == 'missing' and r['stale_evidence_ids'] == r['current_evidence_ids'] == []
               for r in runs(data).values())


@pytest.mark.parametrize('change,reason', [('check', 'check_id_mismatch'),
    ('test', 'test_id_mismatch'), ('subject', 'subject_binding_missing'),
    ('hash', 'configuration_binding_missing'), ('policy', 'configuration_binding_missing'),
    ('configuration', 'configuration_mismatch'), ('independence', 'independent_contract_required')])
def test_ineligible_evidence_explains_exact_key_or_configuration_exclusion(change, reason):
    records, evaluation, cfg, key = case(with_test=True, expected=('ci:observed',),
                                       policy='independent' if change == 'hash' else 'bound')
    item = observation(records, evaluation, key)
    if change == 'check': item['run_context']['check_id'] = 'different'
    if change == 'test': item['run_context']['test_id'] = None
    if change == 'subject': item['subjects'] = [s for s in item['subjects'] if s['artifact_id'] != ref()]
    if change == 'hash':
        # A bound record without its hash is structurally invalid already.
        item['configuration_policy'] = 'independent'
        del item['configuration_hash']
    if change == 'policy': del item['configuration_policy']
    if change == 'configuration': item['configuration_hash'] = 'f' * 64
    if change == 'independence': item['configuration_policy'] = 'independent'
    data = assess(records + [item], evaluation, cfg).data
    excluded = data['checks'][0]['excluded_evidence'][0]
    assert excluded['disposition'] == 'unselected' and excluded['reasons'] == [reason]
    assert excluded['missing_subject_ids'] == ([ref()] if change == 'subject' else [])
    assert runs(data)['ci:observed']['presence'] == 'missing'


@pytest.mark.parametrize('changed_contract', [False, True])
def test_cross_configuration_reuse_checks_actual_current_contract(changed_contract):
    records, evaluation, cfg, key = case(policy='independent')
    item = observation(records, evaluation, key)
    item.update(configuration_policy='independent', configuration_hash='e' * 64)
    if changed_contract: records[1]['oracle'] = 'Changed meaning'
    data = assess(records + [item], evaluation, cfg).data
    if changed_contract:
        assert list(runs(data)) == ['ci:expected']
        assert data['checks'][0]['excluded_evidence'][0]['reasons'] == ['contract_context_changed']
    else:
        candidate = observed(data)
        assert candidate['freshness'] == 'current' and candidate['configuration_hash'] == 'e' * 64
        assert all(c['contract_configuration_independent'] for c in candidate['context_assessments'])


def test_unconfigured_explicit_independence_retains_null_and_freshness():
    records, evaluation, cfg, key = case(policy='independent', configured=False)
    item = observation(records, evaluation, key); item['configuration_policy'] = 'independent'
    candidate = observed(assess(records + [item], evaluation, cfg).data)
    assert candidate['freshness'] == 'current'
    assert all(c['configuration_hash'] is None for c in candidate['context_assessments'])


def test_direct_test_contract_is_assessed_once_per_unique_subject_binding():
    records, evaluation, cfg, key = case(direct=True)
    item = observation(records, evaluation, key)
    candidate = observed(assess(records + [item], evaluation, cfg).data)
    assert candidate['freshness'] == 'current'
    assert [c['subject']['artifact_id'] for c in candidate['context_assessments']] == [ref(), ref('TEST')]


@pytest.mark.parametrize('subject_kind', ['capability', 'task'])
def test_unsupported_context_projection_never_becomes_invented_current_evidence(subject_kind):
    records, evaluation, cfg, key = case(direct=True, subject_kind=subject_kind)
    item = observation(records, evaluation, key)
    # Historical placeholder hashes are not rewritten when a type is admitted.
    next(s for s in item['subjects'] if s['artifact_id'] == key['subject_artifact_id'])[
        'verification_context_sha256'] = 'a' * 64
    data = assess(records + [item], evaluation, cfg).data; candidate = observed(data)
    assert candidate['freshness'] == 'stale'
    assert candidate['unsupported_subject_ids'] == []
    assert candidate['reasons'] == []
    assert runs(data)['ci:observed']['stale_evidence_ids'] == [item['id']]
    assert data['context_freshness_evaluated']


def test_a_shared_evidence_is_assessed_separately_for_each_recorded_subject():
    records, evaluation, cfg, key = case()
    other = domain_value('requirement', id=ref('REQ', '2'), relations=[edge(ref('VER'), 1)])
    records.append(other); records[1]['subjects'].append(other['id'])
    value = evaluation.data
    other_key = {**key, 'subject_artifact_id': other['id']}
    value['required_runs'].append({**other_key, 'run_ids': ['ci:expected']})
    evaluation = VerificationEvaluation(artifact_bytes(value))
    first = observation(records, evaluation, key)
    second = observation(records, evaluation, other_key)
    first['subjects'].append(next(s for s in second['subjects'] if s['artifact_id'] == other['id']))
    other['statement'] = 'Now different'
    data = assess(records + [first], evaluation, cfg).data
    states = dispositions(data)[first['id']]['candidate_checks']
    assert [(s['subject_artifact_id'], s['freshness']) for s in states] == [(ref(), 'current'), (other['id'], 'stale')]


def test_one_run_keeps_multiple_slots_and_their_missing_expectations_separate():
    records, evaluation, cfg, key = case(expected=('ci:observed',))
    records[1]['evidence_slots'].append({'check_id': 'second', 'test_id': None, 'dimension': 'overall'})
    value = evaluation.data
    value['required_runs'].append({**value['required_runs'][0], 'check_id': 'second'})
    evaluation = VerificationEvaluation(artifact_bytes(value))
    item = observation(records, evaluation, key)
    data = assess(records + [item], evaluation, cfg).data
    assert [c['runs'][0]['presence'] for c in data['checks']] == ['present', 'missing']
    assert data['missing_runs'] == [{**key, 'check_id': 'second', 'run_id': 'ci:observed'}]
    assert data['checks'][1]['excluded_evidence'][0]['reasons'] == ['check_id_mismatch']


@pytest.mark.parametrize('result', ['passed', 'failed', 'running', 'not_measured'])
def test_raw_result_never_controls_context_freshness_or_creates_success(result):
    records, evaluation, cfg, key = case(expected=('ci:observed',))
    data = assess(records + [observation(records, evaluation, key, result=result)], evaluation, cfg).data
    assert observed(data)['result'] == result and observed(data)['freshness'] == 'current'
    assert data['missing_runs'] == [] and not data['result_aggregation_evaluated']
    assert 'verification_result' not in data


def test_record_order_evidence_id_order_and_import_time_do_not_select_a_winner():
    records, evaluation, cfg, key = case(expected=('ci:shared',))
    first = observation(records, evaluation, key, run='ci:shared', result='failed')
    second = observation(records, evaluation, key, token='2', run='ci:shared', result='passed')
    stale = observation(records, evaluation, key, token='3', run='ci:shared', result='passed')
    stale['subjects'][0]['verification_context_sha256'] = 'f' * 64
    items = [first, second, stale]
    data = assess(records + items, evaluation, cfg).data
    assert assess(list(reversed(records + items)), evaluation, cfg).data == data
    expected = sorted((e['result'], e['freshness']) for e in runs(data)['ci:shared']['evidence'])
    first['id'], second['id'] = second['id'], first['id']
    first['produced_at'], second['produced_at'] = '2026-10-21T01:00:00Z', '2025-01-01T00:00:00Z'
    reordered = assess(records + items, evaluation, cfg).data
    assert sorted((e['result'], e['freshness']) for e in runs(reordered)['ci:shared']['evidence']) == expected
    assert reordered['missing_runs'] == data['missing_runs'] == []


def test_explicit_scope_is_independent_of_evidence_and_dispositions_do_not_expand_it():
    records, evaluation, cfg, key = case()
    records.append(domain_value('requirement', id=ref('REQ', '2')))
    item = observation(records, evaluation, key); supplied = model(records + [item])
    data = assess_verification_runs(supplied, evaluation, configuration_id=cfg,
        scope_descriptor=scope(ref(), configuration_id=cfg), scope_bindings=bindings_for(supplied)).data
    assert len(data['checks']) == 1 and observed(data)['freshness'] == 'current'


@pytest.mark.parametrize('change', ['none', 'configuration', 'contractless_subject'])
def test_incomplete_coverage_prevents_context_and_missing_run_claims(change):
    records, evaluation, cfg, key = case(); item = observation(records, evaluation, key)
    if change == 'none': evaluation = None
    if change == 'configuration':
        value = evaluation.data; value['configuration_hash'] = None
        evaluation = VerificationEvaluation(artifact_bytes(value))
    if change == 'contractless_subject': records.append(domain_value('requirement', id=ref('REQ', '2')))
    data = assess(records + [item], evaluation, cfg).data
    assert data['checks'] == data['missing_runs'] == data['diagnostics'] == []
    assert data['assessment_status'] == 'incomplete' and not data['context_freshness_evaluated']
    assert dispositions(data)[item['id']]['disposition'] == 'not_evaluated'


def test_cached_descriptor_mutation_cannot_hide_failure_or_expected_missing_run():
    records, evaluation, cfg, key = case(); item = observation(records, evaluation, key)
    before = assess(records + [item], evaluation, cfg).data
    value = evaluation.data; value['required_runs'][0]['run_ids'] = ['ci:observed']
    object.__setattr__(evaluation, '_encoded', canonical_json_bytes(value))
    assert assess(records + [item], evaluation, cfg).data == before


@pytest.mark.parametrize('untyped', [None, {}, 'current-model'])
def test_untyped_model_is_rejected_without_discovery(untyped):
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        assess_verification_runs(untyped, None, configuration_id=None)
    assert caught.value.reason == 'verification_target_model_required'


def test_run_identity_conflict_is_not_downgraded_to_historical_classification():
    records, evaluation, cfg, key = case()
    first = observation(records, evaluation, key)
    second = observation(records, evaluation, key, token='2')
    second['run_context']['subject_state_sha256'] = 'e' * 64
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        assess(records + [first, second], evaluation, cfg)
    assert caught.value.reason == 'evidence_run_identity_conflict'


def test_unqualified_run_identity_is_rejected_instead_of_reported_as_unbound():
    records, evaluation, cfg, key = case()
    item = observation(records, evaluation, key, run='unqualified')
    with pytest.raises(VerificationEvaluationError) as caught:
        assess(records + [item], evaluation, cfg)
    assert caught.value.reason == 'namespaced_evidence_run_id_required'


def test_report_owns_nested_bindings_and_preserves_original_source_bytes():
    records, evaluation, cfg, key = case(); item = observation(records, evaluation, key)
    supplied = model(records + [item]); before = supplied.source_files
    with no_write_attempts(): result = assess_verification_runs(supplied, evaluation, configuration_id=cfg)
    expected = result.data; changed = result.data
    changed['checks'][0]['runs'].clear(); changed['evidence_dispositions'][0]['candidate_checks'].clear()
    item['result'] = 'passed'
    assert result.data == expected and supplied.source_files == before
    assert result.sha256 == canonical_json_sha256(expected)
    assert expected['input_sha256'] == supplied._sources_sha256
    assert expected['evidence_dispositions'][0]['source_sha256'] in {sha256(raw).hexdigest() for raw in before.values()}
    with pytest.raises(TypeError): bool(result)
    with pytest.raises(TypeError): VerificationRunAssessment()
    with pytest.raises(FrozenInstanceError): result._encoded = b'{}'


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_dispositions_and_context_bindings_are_identical_in_isolated_core_and_pyz(mode, tmp_path):
    records, evaluation, cfg, key = case()
    item = observation(records, evaluation, key); records[0]['statement'] = 'Changed requirement'
    historical = observation(records, evaluation, key, token='2', run='ci:historic')
    historical['run_context']['subject_state_sha256'] = 'f' * 64
    supplied = model(records + [item, historical])
    expected = assess_verification_runs(supplied, evaluation, configuration_id=cfg).data
    body = '''import json
from specroad.changes import TargetModel
from specroad.verification import VerificationEvaluation, assess_verification_runs
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
print(json.dumps(assess_verification_runs(owned,evaluation,configuration_id=configuration_id).data))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
