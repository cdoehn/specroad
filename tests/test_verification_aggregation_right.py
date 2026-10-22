"""Mixed obligations obey the public priority table without positive defaults."""
from copy import deepcopy
import json

import pytest

from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.verification import (VerificationEvaluation, VerificationEvaluationError,
    aggregate_verification_results, WaiverReviewVerifier)
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.records import ref
from support.srx import expression_document, literal
from support.targets import model
from test_verification_aggregation import (NOW, DEADLINE, INPUTS, scenario, aggregate,
    subject, waiver_case)
from test_verification_required_checks import edge
from test_verification_required_checks_right import bindings_for, scope
from test_verification_run_replacements import decision, selection
from test_verification_run_selection import observation


KINDS = ('passed', 'failed', 'stale', 'unresolved', 'missing', 'mixed')
# Literal decision tables: rows/columns follow KINDS. P/F/S/I are subject
# results after complete binding, before applying a running plan's priority.
SAME_CHECK = ('PFIIII', 'FFFFFF', 'IFSIII', 'IFIIII', 'IFIIII', 'IFIIII')
SEPARATE_CHECKS = ('PFSIII', 'FFFFFF', 'SFSIII', 'IFIIII', 'IFIIII', 'IFIIII')
RESULT = {'P': 'passed', 'F': 'failed', 'S': 'stale', 'I': 'incomplete'}


def evidence_for(records, evaluation, key, kind, *, run, token):
    parts = {'passed': [('passed', False)], 'failed': [('failed', False)],
        'stale': [('passed', True)], 'unresolved': [('not_measured', False)],
        'missing': [], 'mixed': [('passed', False), ('passed', True)]}[kind]
    items = []
    for index, (result, stale) in enumerate(parts):
        item = observation(records, evaluation, key, run=run, token=str(token + index), result=result)
        if stale:
            item['subjects'][0]['verification_context_sha256'] = 'f' * 64
        items.append(item)
    return items


def pair(left, right, *, separate=False, status='planned'):
    records, evaluation, cfg, key = scenario(status=status, expected=('ci:left', 'ci:right'))
    other_key = key
    if separate:
        records[1]['evidence_slots'].append(
            {'check_id': 'second', 'test_id': None, 'dimension': 'overall'})
        other_key = {**key, 'check_id': 'second'}
        data = evaluation.data
        data['required_runs'] = [{**key, 'run_ids': ['ci:left']},
                                 {**other_key, 'run_ids': ['ci:right']}]
        evaluation = VerificationEvaluation(artifact_bytes(data))
    items = evidence_for(records, evaluation, key, left, run='ci:left', token=1)
    items += evidence_for(records, evaluation, other_key, right, run='ci:right', token=3)
    return records + items, evaluation, cfg


@pytest.mark.parametrize('left', KINDS)
@pytest.mark.parametrize('right', KINDS)
@pytest.mark.parametrize('separate', [False, True], ids=['one-check', 'two-checks'])
@pytest.mark.parametrize('status', ['planned', 'running'])
def test_complete_pair_table_preserves_failure_and_never_defaults_unknown_to_pass(left, right, separate, status):
    records, evaluation, cfg = pair(left, right, separate=separate, status=status)
    table = SEPARATE_CHECKS if separate else SAME_CHECK
    expected = RESULT[table[KINDS.index(left)][KINDS.index(right)]]
    if status == 'running' and expected != 'failed':
        expected = 'running'
    report = aggregate(records, evaluation, cfg)
    data = subject(report)
    assert data['verification_result'] == expected
    assert data['verification_plan_status'] == status
    assert len(data['checks']) == (2 if separate else 1)
    if not separate:
        assert data['checks'][0]['evidence_result'] == RESULT[SAME_CHECK[KINDS.index(left)][KINDS.index(right)]]
    assert not report.data['full_verification_evaluated'] and not report.data['release_readiness_evaluated']


@pytest.mark.parametrize('kind', KINDS)
def test_not_planned_precedes_every_bound_mixed_evidence_result(kind):
    records, evaluation, cfg = pair('failed', kind, separate=True, status='not_planned')
    data = subject(aggregate(records, evaluation, cfg))
    assert data['verification_result'] == 'not_evaluated'
    assert data['checks'][0]['evidence_result'] == 'failed'


@pytest.mark.parametrize('freshness', ['current', 'stale'])
@pytest.mark.parametrize('result', ['running', 'not_measured'])
def test_unresolved_raw_results_are_incomplete_even_in_otherwise_stale_runs(freshness, result):
    records, evaluation, cfg, key = scenario()
    item = observation(records, evaluation, key, run='ci:expected', result=result)
    if freshness == 'stale': item['subjects'][0]['verification_context_sha256'] = 'f' * 64
    data = subject(aggregate(records + [item], evaluation, cfg))
    assert data['verification_result'] == data['checks'][0]['evidence_result'] == 'incomplete'
    run = data['checks'][0]['active_runs'][0]
    assert run['run_result'] == 'incomplete'
    assert run['blocking_observations'][0]['result'] == result
    assert 'evidence_result_incomplete' in run['blocking_observations'][0]['reasons']


@pytest.mark.parametrize('kind', ['capability', 'task'])
@pytest.mark.parametrize('stale_contract', [False, True])
@pytest.mark.parametrize('result', ['passed', 'failed'])
def test_unsupported_subject_context_remains_incomplete_beside_a_stale_test(kind, stale_contract, result):
    records, evaluation, cfg, key = scenario(subject_kind=kind, direct=True)
    item = observation(records, evaluation, key, run='ci:expected', result=result)
    if stale_contract:
        next(s for s in item['subjects'] if s['artifact_id'] == key['test_id'])[
            'verification_context_sha256'] = 'f' * 64
    data = subject(aggregate(records + [item], evaluation, cfg))
    # Retain this permanent test identity; Appendix L now defines both types.
    expected = 'stale' if stale_contract else result
    assert data['verification_result'] == expected
    run = data['checks'][0]['active_runs'][0]
    assert run['run_result'] == expected
    assert run['evidence'][0]['freshness'] == ('stale' if stale_contract else 'current')
    assert run['evidence'][0]['unsupported_subject_ids'] == []


def test_failure_retains_all_other_blocking_observations_of_the_same_run():
    records, evaluation, cfg, key = scenario()
    failed = observation(records, evaluation, key, run='ci:expected')
    stale = observation(records, evaluation, key, token='2', run='ci:expected', result='passed')
    stale['subjects'][0]['verification_context_sha256'] = 'f' * 64
    unresolved = observation(records, evaluation, key, token='3', run='ci:expected', result='running')
    data = subject(aggregate(records + [unresolved, stale, failed], evaluation, cfg))
    run = data['checks'][0]['active_runs'][0]
    assert data['verification_result'] == data['checks'][0]['evidence_result'] == run['run_result'] == 'failed'
    assert {row['evidence_id']: row['reasons'] for row in run['blocking_observations']} == {
        failed['id']: ['current_required_evidence_failed'],
        stale['id']: ['required_evidence_stale'],
        unresolved['id']: ['evidence_result_incomplete']}


def test_mixed_run_freshness_is_explained_without_inventing_a_missing_observation():
    records, evaluation, cfg = pair('passed', 'stale')
    report = aggregate(records, evaluation, cfg)
    data = subject(report); check = data['checks'][0]
    assert data['verification_result'] == check['evidence_result'] == 'incomplete'
    assert data['reasons'] == check['reasons'] == ['required_check_mixed_freshness']
    assert {r['run_id']: r['presence'] for r in check['active_runs']} == {'ci:left': 'present', 'ci:right': 'present'}
    assert report.data['replacement_assessment']['missing_runs'] == []
    assert report.data['diagnostics'][0]['reason'] == 'required_check_mixed_freshness'


@pytest.mark.parametrize('change', ['missing_key', 'configuration', 'missing_contract', 'unknown_applicability'])
def test_incomplete_native_obligations_or_binding_take_precedence_over_known_observations(change):
    records, evaluation, cfg, key = scenario(status='running')
    failed = observation(records, evaluation, key, run='ci:expected')
    expected = {'missing_key': 'required_check_missing', 'configuration': 'evaluation_configuration_mismatch',
                'missing_contract': 'verification_contract_missing',
                'unknown_applicability': 'verification_applicability_unresolved'}[change]
    if change == 'missing_key':
        records[1]['evidence_slots'].append({'check_id': 'other', 'test_id': None, 'dimension': 'overall'})
    if change == 'configuration':
        data = evaluation.data; data['configuration_hash'] = 'a' * 64
        evaluation = VerificationEvaluation(artifact_bytes(data))
    if change == 'missing_contract':
        records.append(domain_value('requirement', id=ref('REQ', '2'), verification_plan_status='planned'))
    if change == 'unknown_applicability':
        records[0]['applicability'] = expression_document(literal(True))
        cfg = None
        data = evaluation.data; data['configuration_hash'] = None
        evaluation = VerificationEvaluation(artifact_bytes(data))
    data = subject(aggregate(records + [failed], evaluation, cfg))
    assert data['verification_result'] == 'incomplete' and expected in data['reasons']
    assert data['checks'] == []


def test_passing_evidence_detail_cannot_override_unavailable_product_input_bytes():
    records, evaluation, cfg, key = scenario()
    records.append(observation(records, evaluation, key, run='ci:expected', result='passed'))
    data = subject(aggregate(records, evaluation, cfg, inputs=None))
    assert data['checks'][0]['evidence_result'] == 'passed'
    assert data['verification_result'] == 'incomplete'


@pytest.mark.parametrize('field', ['configuration_hash', 'test_id', 'check_id', 'subject_binding'])
def test_foreign_success_does_not_fill_a_required_run(field):
    records, evaluation, cfg, key = scenario(with_test=True)
    item = observation(records, evaluation, key, run='ci:expected', result='passed')
    if field == 'configuration_hash': item[field] = 'f' * 64
    elif field == 'subject_binding':
        item['subjects'] = [s for s in item['subjects'] if s['artifact_id'] != key['subject_artifact_id']]
    else: item['run_context'][field] = None if field == 'test_id' else 'different-check'
    data = subject(aggregate(records + [item], evaluation, cfg))
    assert data['verification_result'] == 'incomplete' and data['reasons'] == ['required_run_missing']
    assert data['checks'][0]['active_runs'][0]['evidence'] == []


@pytest.mark.parametrize('terminal', ['passed', 'failed', 'stale', 'unresolved', 'missing', 'mixed'])
def test_replacement_never_launders_a_missing_or_unresolved_terminal(terminal):
    records, evaluation, cfg, key = scenario(expected=('ci:old',))
    old = observation(records, evaluation, key, run='ci:old')
    items = evidence_for(records, evaluation, key, terminal, run='ci:new', token=2)
    evaluation = selection(evaluation, [decision(key, 'ci:old', [old])])
    data = subject(aggregate(records + [old, *items], evaluation, cfg))
    expected = {'passed': 'passed', 'failed': 'failed'}.get(terminal, 'incomplete')
    assert data['verification_result'] == expected
    assert data['checks'][0]['replacements'][0]['effective'] is (terminal in ('passed', 'failed'))
    if expected == 'incomplete': assert data['reasons'] == ['replacement_binding_changed']
    assert old['result'] == 'failed'


@pytest.mark.parametrize('change', ['additional_old', 'changed_old'])
def test_newly_known_old_evidence_invalidates_replacement_before_current_failure(change):
    records, evaluation, cfg, key = scenario(expected=('ci:old',))
    old = observation(records, evaluation, key, run='ci:old')
    new = observation(records, evaluation, key, token='2', run='ci:new', result='passed')
    evaluation = selection(evaluation, [decision(key, 'ci:old', [old])])
    items = [old, new]
    if change == 'additional_old': items.append(observation(records, evaluation, key, token='3', run='ci:old'))
    else: old['environment'] = {'platform': 'changed-historical-environment'}
    data = subject(aggregate(records + items, evaluation, cfg))
    assert data['verification_result'] == 'incomplete' and data['reasons'] == ['replacement_binding_changed']
    assert data['checks'][0]['evidence_result'] == 'failed'


@pytest.mark.parametrize('status', ['planned', 'running', 'not_planned'])
def test_malformed_evaluation_is_rejected_before_any_fachliche_result(status):
    records, evaluation, cfg, _ = scenario(status=status)
    data = evaluation.data; data['required_runs'][0]['run_ids'] = []
    object.__setattr__(evaluation, 'source_bytes', artifact_bytes(data))
    with pytest.raises(VerificationEvaluationError) as caught:
        aggregate(records, evaluation, cfg)
    assert caught.value.code == 'SRV175' and caught.value.exit_code == 3


@pytest.mark.parametrize('field,value', [('subject_id', 'different-product'),
    ('subject_state_sha256', 'f' * 64)])
def test_conflicting_run_identity_is_not_downgraded_to_an_aggregation_result(field, value):
    records, evaluation, cfg, key = scenario(status='not_planned')
    first = observation(records, evaluation, key, run='ci:expected', result='passed')
    second = observation(records, evaluation, key, token='2', run='ci:expected', result='passed')
    second['run_context'][field] = value
    with pytest.raises(ModelError) as caught:
        aggregate(records + [first, second], evaluation, cfg)
    assert caught.value.reason == 'evidence_run_identity_conflict'


@pytest.mark.parametrize('kind,expected', [('missing', 'incomplete'), ('stale', 'stale')])
def test_other_subjects_missing_or_stale_evidence_does_not_spread_to_a_complete_subject(kind, expected):
    records, evaluation, cfg, key = scenario()
    other = domain_value('requirement', id=ref('REQ', '2'), verification_plan_status='planned',
        relations=[edge(key['contract_id'], 1)])
    records[1]['subjects'].append(other['id']); records.append(other)
    other_key = {**key, 'subject_artifact_id': other['id']}
    data = evaluation.data; data['required_runs'].append({**other_key, 'run_ids': ['ci:other']})
    evaluation = VerificationEvaluation(artifact_bytes(data))
    items = evidence_for(records, evaluation, key, 'passed', run='ci:expected', token=1)
    items += evidence_for(records, evaluation, other_key, kind, run='ci:other', token=3)
    report = aggregate(records + items, evaluation, cfg)
    assert {s['subject_artifact_id']: s['verification_result'] for s in report.data['subjects']} == {
        key['subject_artifact_id']: 'passed', other['id']: expected}


def test_scope_is_independent_and_a_waiver_for_a_different_scope_is_not_reused():
    records, evaluation, cfg, key, review, verifier = waiver_case()
    records.append(observation(records, evaluation, key, run='ci:expected'))
    supplied = model(records)
    data = subject(aggregate(records, evaluation, cfg,
        scope_descriptor=scope(key['subject_artifact_id'], configuration_id=cfg),
        scope_bindings=bindings_for(supplied),
        waiver_reviews={key['subject_artifact_id']: review}, waiver_verifier=verifier))
    assert data['verification_result'] == 'failed'
    assert data['waiver_assessment']['reasons'] == ['waiver_scope_mismatch']


@pytest.mark.parametrize('time,expected', [
    ('2026-10-21T23:59:59.999999999Z', 'waived'),
    (DEADLINE, 'failed'), ('2026-10-22T00:00:00.000000001Z', 'failed')])
def test_aggregation_uses_explicit_exact_waiver_deadline(time, expected):
    records, evaluation, cfg, key, review, verifier = waiver_case()
    records.append(observation(records, evaluation, key, run='ci:expected'))
    data = subject(aggregate(records, evaluation, cfg, evaluated_at=time,
        waiver_reviews={key['subject_artifact_id']: review}, waiver_verifier=verifier))
    assert data['verification_result'] == expected
    assert data['checks'][0]['evidence_result'] == 'failed'


def test_configuration_exclusion_does_not_invoke_a_waiver_host_or_override_structural_errors():
    records, evaluation, cfg, key, review, _ = waiver_case()
    records[0]['applicability'] = expression_document(literal(False))
    def forbidden(*args):
        raise AssertionError('Excluded subjects do not request a review verification')
    verifier = WaiverReviewVerifier('explicit-test-host', '1', forbidden)
    data = subject(aggregate(records, None, cfg, waiver_reviews={key['subject_artifact_id']: review},
        waiver_verifier=verifier, inputs=None, input_roles=None))
    assert data['verification_result'] == 'not_applicable' and data['waiver_assessment'] is None
    broken = evaluation.data; broken['unknown'] = True
    object.__setattr__(evaluation, 'source_bytes', artifact_bytes(broken))
    with pytest.raises(VerificationEvaluationError):
        aggregate(records, evaluation, cfg, waiver_reviews={key['subject_artifact_id']: review},
                  waiver_verifier=verifier)


@pytest.mark.parametrize('reviews', [True, [], {'untyped': {}}, {1: None}])
def test_waiver_claims_cannot_enter_as_untyped_or_truthy_values(reviews):
    records, evaluation, cfg, _ = scenario()
    with pytest.raises(ModelError): aggregate(records, evaluation, cfg, waiver_reviews=reviews)


def test_unrelated_waiver_review_cannot_expand_the_selected_scope():
    records, evaluation, cfg, _, review, verifier = waiver_case()
    with pytest.raises(ModelError) as caught:
        aggregate(records, evaluation, cfg, waiver_reviews={ref('REQ', '9'): review}, waiver_verifier=verifier)
    assert caught.value.reason == 'verification_waiver_review_outside_scope'


def test_result_and_blocker_details_are_owned_order_independent_and_write_free():
    records, evaluation, cfg = pair('mixed', 'unresolved', separate=True)
    original = deepcopy(records); raw = evaluation.source_bytes
    with no_write_attempts():
        report = aggregate(records, evaluation, cfg)
        reversed_report = aggregate(list(reversed(records)), evaluation, cfg)
    assert report.data == reversed_report.data and report.sha256 == reversed_report.sha256
    assert records == original and evaluation.source_bytes == raw
    value = report.data
    assert canonical_json_sha256(value) == report.sha256
    value['subjects'][0]['checks'][0]['active_runs'][0]['blocking_observations'].clear()
    assert subject(report)['checks'][0]['active_runs'][0]['blocking_observations']
    assert not any(report.data[k] for k in ('project_files_verified',
        'evaluation_identity_history_checked', 'external_run_verified', 'release_readiness_evaluated',
        'input_roles_authenticated', 'test_code_executed', 'write_authorized', 'approval_granted'))


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_mixed_blocker_report_matches_in_isolated_core_and_pyz(mode, tmp_path):
    records, evaluation, cfg = pair('mixed', 'unresolved', separate=True)
    supplied = model(records); expected = aggregate(records, evaluation, cfg).data
    body = '''import json
from specroad.changes import TargetModel
from specroad.verification import VerificationEvaluation, aggregate_verification_results
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
'''
    body += 'config=' + repr(supplied.configuration_bytes) + '\n'
    body += 'documents=' + repr([(d.path, d.content) for d in supplied.documents]) + '\n'
    body += 'resources=' + repr([(d.path, d.content) for d in supplied.resource_files]) + '\n'
    body += 'core_key=' + repr(supplied.profile.profile_chain[0]) + '\n'
    body += 'evaluation=VerificationEvaluation(' + repr(evaluation.source_bytes) + ')\n'
    body += 'configuration_id=' + repr(cfg) + '\ninputs=' + repr(INPUTS) + '\nnow=' + repr(NOW) + '\n'
    body += '''profile=compose_profiles([ProfileResource(raw) for path,raw in resources],core_key=core_key)
owned=TargetModel(config,ProjectReadBinding('sample','/explicit/provider',(1,2)),
 [ModelDocument(path,raw) for path,raw in documents],profile=profile,
 resource_files=[ModelDocument(path,raw) for path,raw in resources])
print(json.dumps(aggregate_verification_results(owned,evaluation,configuration_id=configuration_id,
 inputs=inputs,input_roles={p:'input' for p in inputs},evaluated_at=now).data))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
