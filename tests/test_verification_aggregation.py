"""Bound per-subject priority results without altering Evidence or granting rights."""
from dataclasses import FrozenInstanceError
import json

import pytest

from specroad.configurations import resolve_configuration
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.storage.domain_artifact import DomainArtifact
from specroad.verification import (VerificationEvaluation, VerificationEvaluationError,
    VerificationReplacementAuthorityError, VerificationResultAggregation,
    aggregate_verification_results, assess_run_replacements, resolve_required_checks,
    prepare_verification_waiver, WaiverContext, HumanWaiverReview,
    WaiverReviewVerifier, WaiverReviewVerification)
from support.artifacts import artifact_bytes
from support.domain import domain_value, waiver as legacy_waiver
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.records import ref
from support.srx import expression_document, literal
from support.targets import model
from test_verification_evaluation import INPUTS
from test_verification_required_checks import edge
from test_verification_run_selection import case, observation
from test_verification_run_replacements import decision, selection

NOW = '2026-10-21T00:00:00Z'
DEADLINE = '2026-10-22T00:00:00Z'
HUMAN = {'actor_type': 'human', 'actor_id': 'declared-reviewer'}


def scenario(*, status='planned', **kwargs):
    records, evaluation, cfg, key = case(**kwargs)
    records[0]['verification_plan_status'] = status
    return records, evaluation, cfg, key


def aggregate(records, evaluation, cfg, **kwargs):
    options = {'configuration_id': cfg, 'inputs': dict(INPUTS),
        'input_roles': {path: 'input' for path in INPUTS}, 'evaluated_at': NOW}
    options.update(kwargs)
    return aggregate_verification_results(model(records), evaluation, **options)


def subject(report):
    return report.data['subjects'][0]


@pytest.mark.parametrize('status,result,freshness,expected', [
    ('planned', 'passed', 'current', 'passed'),
    ('planned', 'failed', 'current', 'failed'),
    ('running', 'failed', 'current', 'failed'),
    ('running', 'passed', 'current', 'running'),
    ('not_planned', 'failed', 'current', 'not_evaluated'),
    ('planned', 'passed', 'stale', 'stale'),
    ('planned', 'running', 'current', 'incomplete'),
    ('planned', 'not_measured', 'current', 'incomplete'),
    ('planned', None, None, 'incomplete'),
    ('not_applicable', 'passed', 'current', 'passed'),
])
def test_explicit_plan_and_actual_observations_follow_result_priorities(status, result, freshness, expected):
    records, evaluation, cfg, key = scenario(status=status)
    if result is not None:
        item = observation(records, evaluation, key, run='ci:expected', result=result)
        if freshness == 'stale': item['subjects'][0]['verification_context_sha256'] = 'f' * 64
        records.append(item)
    report = aggregate(records, evaluation, cfg)
    assert subject(report)['verification_result'] == expected
    assert subject(report)['verification_plan_status'] == status
    assert not any(report.data[f] for f in ('project_files_verified',
        'project_required_checks_complete', 'evaluation_identity_history_checked',
        'full_verification_evaluated',
        'release_readiness_evaluated', 'external_run_verified', 'test_code_executed',
        'write_authorized', 'approval_granted'))


@pytest.mark.parametrize('status', ['planned', 'running'])
def test_current_failure_wins_over_later_pass_and_other_missing_expected_run(status):
    records, evaluation, cfg, key = scenario(status=status, expected=('ci:old', 'ci:missing'))
    old = observation(records, evaluation, key, run='ci:old')
    new = observation(records, evaluation, key, token='2', run='ci:new', result='passed',
                      produced_at='2026-10-21T01:00:00Z')
    report = aggregate(records + [new, old], evaluation, cfg)
    assert subject(report)['verification_result'] == 'failed'
    runs = subject(report)['checks'][0]['active_runs']
    assert {r['run_id']: r['run_result'] for r in runs} == {
        'ci:missing': 'incomplete', 'ci:new': 'passed', 'ci:old': 'failed'}
    assert report.data['replacement_assessment']['missing_runs'][0]['run_id'] == 'ci:missing'


def test_all_observations_of_one_run_participate_without_a_newest_success_rule():
    records, evaluation, cfg, key = scenario()
    failed = observation(records, evaluation, key, run='ci:expected')
    passed = observation(records, evaluation, key, token='2', run='ci:expected', result='passed')
    data = subject(aggregate(records + [passed, failed], evaluation, cfg))
    assert data['verification_result'] == 'failed'
    run = data['checks'][0]['active_runs'][0]
    assert run['run_result'] == 'failed' and len(run['evidence']) == 2
    assert [e['result'] for e in run['evidence']] == ['failed', 'passed']


@pytest.mark.parametrize('change', ['descriptor', 'bytes', 'roles', 'changed_bytes', 'missing_file'])
def test_passed_evidence_cannot_replace_required_evaluation_input_binding(change):
    records, evaluation, cfg, key = scenario()
    item = observation(records, evaluation, key, run='ci:expected', result='passed')
    options = {}
    if change == 'descriptor': evaluation = None
    if change == 'bytes': options['inputs'] = None
    if change == 'roles': options['input_roles'] = None
    if change == 'changed_bytes': options['inputs'] = {**INPUTS, 'src/program.py': b'return 2\n'}
    if change == 'missing_file': options['inputs'] = {}
    report = aggregate(records + [item], evaluation, cfg, **options)
    assert subject(report)['verification_result'] == 'incomplete'
    assert report.data['diagnostics'] and all(d['code'] == 'SRV176' for d in report.data['diagnostics'])
    if change == 'descriptor': assert subject(report)['reasons'] == ['evaluation_required']


def test_forbidden_input_role_stays_a_structured_error_even_before_not_planned_result():
    records, evaluation, cfg, _ = scenario(status='not_planned')
    with pytest.raises(VerificationEvaluationError) as caught:
        aggregate(records, evaluation, cfg, input_roles={p: 'evidence' for p in INPUTS})
    assert caught.value.code == 'SRV175' and caught.value.exit_code == 3


@pytest.mark.parametrize('status', ['planned', 'not_planned', 'running'])
def test_configuration_exclusion_has_priority_without_a_descriptor_or_product_bytes(status):
    records, _, cfg, _ = scenario(status=status)
    records[0]['applicability'] = expression_document(literal(False))
    report = aggregate(records, None, cfg, inputs=None, input_roles=None)
    assert subject(report)['verification_result'] == 'not_applicable'
    assert subject(report)['checks'] == [] and subject(report)['applicability']['status'] == 'excluded'


def waiver_case():
    records, evaluation, cfg, key = scenario()
    scope = ScopeDescriptor(resolve_required_checks(model(records), configuration_id=cfg).data['scope_descriptor'])
    configuration = resolve_configuration([SourceRelations(artifact_bytes(v)) for v in records], cfg)
    original = DomainArtifact(artifact_bytes(records[0]))
    waiver = prepare_verification_waiver(WaiverContext(original, scope,
        evaluated_at=NOW, configuration=configuration), reason='Approved temporary exception',
        expires_at=DEADLINE, human_review_id='human:aggregation-waiver')
    records[0].update(verification_plan_status='waived', verification_waiver=waiver.data)
    review = HumanWaiverReview({'review_id': 'human:aggregation-waiver', 'subject_id': original.id,
        'waiver_sha256': waiver.sha256, 'reviewer': HUMAN, 'reviewed_at': NOW, 'decision': 'confirmed'})
    verifier = WaiverReviewVerifier('explicit-test-host', '1', lambda ctx, human:
        WaiverReviewVerification(ctx.sha256, human.sha256, True, True))
    return records, evaluation, cfg, key, review, verifier


def test_exact_current_human_waiver_precedes_failure_and_is_not_passed():
    records, evaluation, cfg, key, review, verifier = waiver_case()
    failed = observation(records, evaluation, key, run='ci:expected')
    report = aggregate(records + [failed], evaluation, cfg, inputs=None, input_roles=None,
        waiver_reviews={key['subject_artifact_id']: review}, waiver_verifier=verifier)
    data = subject(report)
    assert data['verification_result'] == 'waived' and data['waiver_assessment']['review_verified']
    assert data['checks'][0]['active_runs'][0]['run_result'] == 'failed'
    assert not report.data['input_bytes_verified'] and not report.data['release_readiness_evaluated']


@pytest.mark.parametrize('change', ['expired', 'missing_verifier', 'missing_review', 'changed_content'])
def test_ineffective_waiver_does_not_hide_a_current_failure(change):
    records, evaluation, cfg, key, review, verifier = waiver_case()
    if change == 'changed_content': records[0]['statement'] = 'New required behavior'
    failed = observation(records, evaluation, key, run='ci:expected')
    options = {'waiver_reviews': {key['subject_artifact_id']: review}, 'waiver_verifier': verifier}
    if change == 'expired': options['evaluated_at'] = DEADLINE
    if change == 'missing_verifier': options['waiver_verifier'] = None
    if change == 'missing_review': options['waiver_reviews'] = None
    data = subject(aggregate(records + [failed], evaluation, cfg, **options))
    assert data['verification_result'] == 'failed' and data['waiver_assessment']['waiver_result'] == 'ineffective'
    assert data['waiver_assessment']['reasons']


def test_legacy_waiver_with_free_text_is_not_an_effective_exception():
    records, evaluation, cfg, _ = scenario(status='waived')
    records[0]['verification_waiver'] = legacy_waiver()
    data = subject(aggregate(records, evaluation, cfg))
    assert data['verification_result'] == 'incomplete'
    assert 'legacy_waiver_unsupported' in data['waiver_assessment']['reasons']


@pytest.mark.parametrize('result', ['passed', 'failed'])
def test_valid_retest_uses_only_effective_runs_and_keeps_failed_terminal_failed(result):
    records, evaluation, cfg, key = scenario(expected=('ci:old',))
    old = observation(records, evaluation, key, run='ci:old')
    new = observation(records, evaluation, key, token='2', run='ci:new', result=result)
    evaluation = selection(evaluation, [decision(key, 'ci:old', [old])])
    report = aggregate(records + [old, new], evaluation, cfg)
    data = subject(report)
    assert data['verification_result'] == result
    assert data['checks'][0]['effective_expected_run_ids'] == ['ci:new']
    assert data['checks'][0]['superseded_run_ids'] == ['ci:old']
    assert [r['run_id'] for r in data['checks'][0]['active_runs']] == ['ci:new']
    assert old['result'] == 'failed'


def test_invalid_replacement_has_priority_over_old_failure_and_running_status():
    records, evaluation, cfg, key = scenario(status='running', expected=('ci:old',))
    old = observation(records, evaluation, key, run='ci:old')
    evaluation = selection(evaluation, [decision(key, 'ci:old', [old])])
    data = subject(aggregate(records + [old], evaluation, cfg))
    assert data['verification_result'] == 'incomplete' and data['reasons'] == ['replacement_binding_changed']
    assert data['checks'][0]['active_runs'][0]['run_result'] == 'failed'


@pytest.mark.parametrize('change', ['stale', 'running'])
def test_current_pass_cannot_discard_an_unresolved_observation_of_the_same_run(change):
    records, evaluation, cfg, key = scenario()
    passed = observation(records, evaluation, key, run='ci:expected', result='passed')
    other = observation(records, evaluation, key, token='2', run='ci:expected', result='passed')
    if change == 'stale': other['subjects'][0]['verification_context_sha256'] = 'f' * 64
    else: other['result'] = 'running'
    data = subject(aggregate(records + [passed, other], evaluation, cfg))
    assert data['verification_result'] == 'incomplete'


@pytest.mark.parametrize('change', ['historical', 'unbound'])
def test_foreign_or_unbound_success_never_satisfies_a_missing_expected_run(change):
    records, evaluation, cfg, key = scenario()
    item = observation(records, evaluation, key, run='ci:expected', result='passed')
    if change == 'historical': item['run_context']['subject_state_sha256'] = 'a' * 64
    else: item.update(run_context=None, unbound_reason='Origin not supplied')
    data = subject(aggregate(records + [item], evaluation, cfg))
    assert data['verification_result'] == 'incomplete' and data['reasons'] == ['required_run_missing']


def test_per_subject_results_do_not_spread_failure_to_another_fully_bound_subject():
    records, evaluation, cfg, key = scenario()
    other = domain_value('requirement', id=ref('REQ', '2'), verification_plan_status='planned',
        relations=[edge(key['contract_id'], 1)])
    records[1]['subjects'].append(other['id']); records.append(other)
    other_key = {**key, 'subject_artifact_id': other['id']}
    data = evaluation.data; data['required_runs'].append({**other_key, 'run_ids': ['ci:second']})
    evaluation = VerificationEvaluation(artifact_bytes(data))
    failure = observation(records, evaluation, key, run='ci:expected')
    success = observation(records, evaluation, other_key, token='2', run='ci:second', result='passed')
    report = aggregate(records + [failure, success], evaluation, cfg)
    assert {s['subject_artifact_id']: s['verification_result'] for s in report.data['subjects']} == {
        key['subject_artifact_id']: 'failed', other['id']: 'passed'}


def test_no_descriptor_does_not_prevent_not_planned_but_is_not_an_inferred_evaluation():
    records, _, cfg, _ = scenario(status='not_planned')
    report = aggregate(records, None, cfg, inputs=None, input_roles=None)
    assert subject(report)['verification_result'] == 'not_evaluated'
    assert report.data['evaluation_sha256'] is None


def test_nonhuman_replacement_remains_code_seven_before_aggregation():
    records, evaluation, cfg, key = scenario(status='not_planned', expected=('ci:old',))
    old = observation(records, evaluation, key, run='ci:old')
    row = decision(key, 'ci:old', [old]); row['authorized_by']['actor_type'] = 'ai'
    value = evaluation.data; value['replacements'] = [row]
    object.__setattr__(evaluation, 'source_bytes', artifact_bytes(value))
    with pytest.raises(VerificationReplacementAuthorityError) as caught:
        aggregate(records + [old], evaluation, cfg)
    assert caught.value.code == 'SRV175' and caught.value.exit_code == 7


@pytest.mark.parametrize('time', [None, '2026-10-21', '2026-10-21T00:00:00+00:00'])
def test_evaluation_time_is_explicit_machine_readable_utc_even_without_active_waiver(time):
    records, evaluation, cfg, _ = scenario()
    with pytest.raises(ModelError): aggregate(records, evaluation, cfg, evaluated_at=time)


def test_owned_result_preserves_original_bytes_native_selection_and_hashes():
    records, evaluation, cfg, key = scenario()
    records.append(observation(records, evaluation, key, run='ci:expected', result='passed'))
    supplied = model(records); before = supplied.source_files; original = evaluation.source_bytes
    with no_write_attempts():
        report = aggregate_verification_results(supplied, evaluation, configuration_id=cfg,
            inputs=INPUTS, input_roles={p: 'input' for p in INPUTS}, evaluated_at=NOW)
    value = report.data
    assert supplied.source_files == before and evaluation.source_bytes == original
    assert all('verification_result' not in json.loads(raw) for raw in before.values())
    assert value['replacement_assessment'] == assess_run_replacements(supplied, evaluation, configuration_id=cfg).data
    assert value['replacement_assessment_sha256'] == canonical_json_sha256(value['replacement_assessment'])
    assert value['input_binding_sha256'] == canonical_json_sha256(value['input_binding'])
    assert report.sha256 == canonical_json_sha256(value) and value['input_bytes_verified'] and value['input_roles_checked']
    value['subjects'][0]['verification_result'] = 'failed'
    assert subject(report)['verification_result'] == 'passed'
    with pytest.raises(TypeError): bool(report)
    with pytest.raises(TypeError): VerificationResultAggregation({})
    with pytest.raises(FrozenInstanceError): report._encoded = b'{}'


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_prioritized_results_match_in_isolated_core_and_pyz(mode, tmp_path):
    records, evaluation, cfg, key = scenario(status='running', expected=('ci:failed', 'ci:missing'))
    records.append(observation(records, evaluation, key, run='ci:failed'))
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
