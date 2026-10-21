"""Explicit synthetic human decisions bind complete old Evidence and end runs."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.verification import (VerificationEvaluation, VerificationEvaluationError,
    VerificationReplacementAuthorityError, VerificationReplacementAssessment,
    assess_run_replacements, assess_verification_runs)
from support.artifacts import artifact_bytes
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.records import ref
from support.targets import model
from test_verification_evaluation import ACTOR, CREATED_AT, descriptor
from test_verification_run_selection import case, observation


def decision(key, old, evidence, targets=('ci:new',)):
    # Independent literal oracle for the ordered full immutable artifact set.
    entries = sorted([{'id': e['id'], 'sha256': canonical_json_sha256(e)} for e in evidence],
                     key=lambda entry: entry['id'].encode('utf-8'))
    raw = json.dumps(entries, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
    return {**key, 'replaced_run_id': old, 'replaced_evidence_set_sha256': sha256(raw).hexdigest(),
        'replacement_run_ids': list(targets), 'reason': 'Human declared same-product retest',
        'authorized_at': CREATED_AT, 'authorized_by': dict(ACTOR)}


def selection(evaluation, decisions):
    data = evaluation.data
    data['evaluation_id'] = 'EVAL-' + '0' * 25 + '2'
    data['replacements'] = decisions
    return VerificationEvaluation(artifact_bytes(data))


def retest(*, expected=('ci:old',), direct=False):
    records, evaluation, cfg, key = case(expected=expected, direct=direct)
    old = observation(records, evaluation, key, run='ci:old')
    new = observation(records, evaluation, key, token='2', run='ci:new', result='passed')
    row = decision(key, 'ci:old', [old])
    return records, evaluation, cfg, key, old, new, row


def assess(records, evaluation, cfg):
    return assess_run_replacements(model(records), evaluation, configuration_id=cfg)


def check(data):
    return data['checks'][0]


@pytest.mark.parametrize('direct', [False, True])
def test_human_same_product_retest_replaces_exactly_old_expected_run_and_keeps_bytes(direct):
    records, evaluation, cfg, key, old, new, row = retest(direct=direct)
    evaluation = selection(evaluation, [row]); supplied = model(records + [new, old])
    before = supplied.source_files
    with no_write_attempts():
        report = assess_run_replacements(supplied, evaluation, configuration_id=cfg)
    data = report.data; chosen = check(data)
    assert chosen['expected_run_ids'] == ['ci:old']
    assert chosen['effective_expected_run_ids'] == chosen['active_run_ids'] == ['ci:new']
    assert chosen['superseded_run_ids'] == ['ci:old']
    replacement = chosen['replacements'][0]
    assert replacement['decision'] == row and replacement['effective']
    assert replacement['actual_evidence_set_sha256'] == row['replaced_evidence_set_sha256']
    assert replacement['evidence_set'] == [{'id': old['id'], 'sha256': canonical_json_sha256(old)}]
    assert replacement['terminal_run_ids'] == ['ci:new'] and replacement['binding_issues'] == []
    assert data['missing_runs'] == data['diagnostics'] == []
    assert data['assessment_status'] == 'assessed' and data['verification_result'] is None
    assert data['assessment'] == assess_verification_runs(supplied, evaluation, configuration_id=cfg).data
    assert data['assessment_sha256'] == canonical_json_sha256(data['assessment'])
    assert data['evaluation_sha256'] == evaluation.sha256 and data['input_sha256'] == supplied._sources_sha256
    assert supplied.source_files == before and old['result'] == 'failed'
    assert data['run_replacements_evaluated']
    assert not any(data[f] for f in ('human_identity_authenticated', 'input_bytes_verified',
        'input_roles_verified', 'project_files_verified', 'project_required_checks_complete',
        'result_aggregation_evaluated', 'full_verification_evaluated', 'external_run_verified',
        'release_readiness_evaluated', 'test_code_executed', 'write_authorized', 'approval_granted'))


def test_without_explicit_replacement_later_success_never_removes_failure():
    records, evaluation, cfg, key, old, new, row = retest()
    data = assess(records + [new, old], evaluation, cfg).data
    assert check(data)['active_run_ids'] == ['ci:new', 'ci:old']
    assert check(data)['effective_expected_run_ids'] == ['ci:old']
    assert check(data)['superseded_run_ids'] == check(data)['replacements'] == []
    assert data['verification_result'] is None and not data['result_aggregation_evaluated']


def test_observed_old_run_can_be_replaced_without_dropping_another_concurrent_failure():
    records, evaluation, cfg, key, old, new, row = retest(expected=('ci:new',))
    concurrent = observation(records, evaluation, key, token='3', run='ci:concurrent')
    data = assess(records + [old, new, concurrent], selection(evaluation, [row]), cfg).data
    assert check(data)['active_run_ids'] == ['ci:concurrent', 'ci:new']
    assert check(data)['superseded_run_ids'] == ['ci:old']
    assert check(data)['effective_expected_run_ids'] == ['ci:new']
    all_results = [e['result'] for r in data['assessment']['checks'][0]['runs'] for e in r['evidence']]
    assert all_results.count('failed') == 2 and not data['result_aggregation_evaluated']


def test_all_old_evidence_is_hashed_in_id_order_and_preserved_in_native_inventory():
    records, evaluation, cfg, key, old, new, row = retest()
    additional = observation(records, evaluation, key, token='3', run='ci:old', result='passed')
    row = decision(key, 'ci:old', [additional, old])
    data = assess(records + [additional, new, old], selection(evaluation, [row]), cfg).data
    replacement = check(data)['replacements'][0]
    assert replacement['effective']
    assert replacement['evidence_set'] == [
        {'id': item['id'], 'sha256': canonical_json_sha256(item)} for item in (old, additional)]
    assert len(data['assessment']['evidence_dispositions']) == 3


def test_acyclic_chain_and_branch_substitute_all_reachable_terminal_runs():
    records, evaluation, cfg, key, old, new, row = retest()
    third = observation(records, evaluation, key, token='3', run='ci:third', result='passed')
    fourth = observation(records, evaluation, key, token='4', run='ci:fourth', result='failed')
    first = decision(key, 'ci:old', [old], ('ci:new', 'ci:fourth'))
    second = decision(key, 'ci:new', [new], ('ci:third',))
    data = assess(records + [old, new, third, fourth], selection(evaluation, [first, second]), cfg).data
    chosen = check(data)
    assert chosen['superseded_run_ids'] == ['ci:new', 'ci:old']
    assert chosen['active_run_ids'] == chosen['effective_expected_run_ids'] == ['ci:fourth', 'ci:third']
    assert all(r['effective'] for r in chosen['replacements'])
    assert data['missing_runs'] == [] and data['verification_result'] is None
    failed = next(r for r in data['assessment']['checks'][0]['runs'] if r['run_id'] == 'ci:fourth')
    assert failed['evidence'][0]['result'] == 'failed'


def test_replacement_never_applies_to_another_slot_with_the_same_run_id():
    records, evaluation, cfg, key, old, new, row = retest()
    records[1]['evidence_slots'].append({'check_id': 'second', 'test_id': None, 'dimension': 'overall'})
    value = evaluation.data; value['required_runs'].append({**key, 'check_id': 'second', 'run_ids': ['ci:old']})
    evaluation = VerificationEvaluation(artifact_bytes(value))
    # The changed Contract needs fresh Evidence contexts for both slots.
    old = observation(records, evaluation, key, run='ci:old')
    new = observation(records, evaluation, key, token='2', run='ci:new', result='passed')
    other = observation(records, evaluation, {**key, 'check_id': 'second'}, token='3', run='ci:old')
    row = decision(key, 'ci:old', [old])
    data = assess(records + [old, new, other], selection(evaluation, [row]), cfg).data
    first, second = data['checks']
    assert first['superseded_run_ids'] == ['ci:old'] and first['active_run_ids'] == ['ci:new']
    assert second['superseded_run_ids'] == [] and second['active_run_ids'] == ['ci:old']


@pytest.mark.parametrize('result', ['passed', 'failed'])
def test_complete_current_terminal_results_are_preserved_without_claiming_a_pass(result):
    records, evaluation, cfg, key, old, new, row = retest()
    new['result'] = result
    data = assess(records + [old, new], selection(evaluation, [row]), cfg).data
    assert check(data)['replacements'][0]['effective'] and check(data)['active_run_ids'] == ['ci:new']
    assert next(r for r in data['assessment']['checks'][0]['runs'] if r['run_id'] == 'ci:new')['evidence'][0]['result'] == result
    assert data['verification_result'] is None and not data['result_aggregation_evaluated']


@pytest.mark.parametrize('change', ['extra_old', 'changed_hash', 'missing_new', 'stale_new', 'unfinished_new'])
def test_unbound_or_incomplete_replacement_retains_old_candidate_and_reports_incomplete(change):
    records, evaluation, cfg, key, old, new, row = retest()
    items = [old, new]
    if change == 'extra_old': items.append(observation(records, evaluation, key, token='3', run='ci:old'))
    if change == 'changed_hash': row['replaced_evidence_set_sha256'] = 'f' * 64
    if change == 'missing_new': items.remove(new)
    if change == 'stale_new': new['subjects'][0]['verification_context_sha256'] = 'f' * 64
    if change == 'unfinished_new': new['result'] = 'running'
    data = assess(records + items, selection(evaluation, [row]), cfg).data
    assert not check(data)['replacements'][0]['effective']
    assert check(data)['superseded_run_ids'] == [] and 'ci:old' in check(data)['active_run_ids']
    assert check(data)['effective_expected_run_ids'] == ['ci:old']
    assert data['verification_result'] == data['assessment_status'] == 'incomplete'
    assert data['diagnostics'][0]['reason'] == 'replacement_binding_changed'
    assert data['diagnostics'][0]['code'] == 'SRV176' and old['result'] == 'failed'


def test_additional_old_record_with_other_configuration_still_changes_the_authorized_set():
    records, evaluation, cfg, key, old, new, row = retest()
    extra = observation(records, evaluation, key, token='3', run='ci:old')
    extra['configuration_hash'] = 'f' * 64
    data = assess(records + [old, new, extra], selection(evaluation, [row]), cfg).data
    replaced = check(data)['replacements'][0]
    assert not replaced['effective'] and len(replaced['evidence_set']) == 2
    assert data['verification_result'] == 'incomplete'


@pytest.mark.parametrize('field', ['subject_artifact_id', 'contract_id', 'test_id', 'check_id',
    'replaced_run_id', 'replaced_evidence_set_sha256', 'replacement_run_ids', 'reason', 'authorized_at', 'authorized_by'])
def test_every_replacement_field_is_required(field):
    _, evaluation, _, _, _, _, row = retest()
    del row[field]
    with pytest.raises(VerificationEvaluationError) as caught:
        selection(evaluation, [row])
    assert caught.value.code == 'SRV175' and caught.value.exit_code == 3


@pytest.mark.parametrize('change', ['extra_field', 'empty_targets', 'duplicate_target', 'self', 'duplicate_old',
    'cycle', 'bare_old', 'bare_target', 'foreign_key', 'empty_reason'])
def test_invalid_replacement_structure_is_rejected_before_any_effect(change):
    _, evaluation, _, _, _, _, row = retest()
    rows = [row]
    if change == 'extra_field': row['unexpected'] = True
    if change == 'empty_targets': row['replacement_run_ids'] = []
    if change == 'duplicate_target': row['replacement_run_ids'] = ['ci:new', 'ci:new']
    if change == 'self': row['replacement_run_ids'] = ['ci:old']
    if change == 'duplicate_old': rows.append(deepcopy(row))
    if change == 'cycle': rows.append({**row, 'replaced_run_id': 'ci:new', 'replacement_run_ids': ['ci:old']})
    if change == 'bare_old': row['replaced_run_id'] = 'old'
    if change == 'bare_target': row['replacement_run_ids'] = ['new']
    if change == 'foreign_key': row['check_id'] = 'not_required'
    if change == 'empty_reason': row['reason'] = '  '
    with no_write_attempts(), pytest.raises(VerificationEvaluationError) as caught:
        selection(evaluation, rows)
    assert caught.value.code == 'SRV175' and caught.value.exit_code == 3


def test_ai_authorization_is_a_security_refusal_not_a_human_replacement():
    _, evaluation, _, _, _, _, row = retest()
    row['authorized_by'] = {'actor_type': 'ai', 'actor_id': 'synthetic-agent'}
    with pytest.raises(VerificationReplacementAuthorityError) as caught:
        selection(evaluation, [row])
    assert caught.value.diagnostic()['code'] == 'SRV175' and caught.value.exit_code == 7
    assert caught.value.reason == 'human_run_replacement_required'


def test_descriptor_hash_normalizes_replacement_order_and_binds_decisions_without_changing_product():
    _, evaluation, _, _, old, new, row = retest()
    second = {**row, 'replaced_run_id': 'ci:new', 'replacement_run_ids': ['ci:z', 'ci:a']}
    one = selection(evaluation, [row, second])
    two = selection(evaluation, [{**second, 'replacement_run_ids': ['ci:a', 'ci:z']}, row])
    assert one.canonical_bytes == two.canonical_bytes and one.sha256 == two.sha256
    assert one.state_sha256 == evaluation.state_sha256 and one.sha256 != evaluation.sha256
    assert [r['replaced_run_id'] for r in one.data['replacements']] == ['ci:new', 'ci:old']
    changed = selection(evaluation, [{**row, 'reason': 'Different declared reason'}])
    assert changed.sha256 != selection(evaluation, [row]).sha256


def test_prepare_accepts_explicit_decisions_and_preserves_legacy_empty_default():
    base = descriptor(); key = {k: v for k, v in base.data['required_runs'][0].items() if k != 'run_ids'}
    row = {**key, 'replaced_run_id': 'meter:first', 'replacement_run_ids': ['meter:second'],
        'replaced_evidence_set_sha256': 'a' * 64, 'reason': 'Declared retest',
        'authorized_at': CREATED_AT, 'authorized_by': ACTOR}
    assert descriptor(replacements=[row]).data['replacements'] == [row]
    assert base.data['replacements'] == []


@pytest.mark.parametrize('change', ['none', 'configuration'])
def test_unavailable_binding_never_grants_any_replacement(change):
    records, evaluation, cfg, key, old, new, row = retest()
    evaluation = selection(evaluation, [row])
    if change == 'none': evaluation = None
    else:
        data = evaluation.data; data['configuration_hash'] = None
        evaluation = VerificationEvaluation(artifact_bytes(data))
    data = assess(records + [old, new], evaluation, cfg).data
    assert data['verification_result'] == 'incomplete' and data['checks'] == []
    assert not data['run_replacements_evaluated'] and data['diagnostics']


def test_owned_report_reparses_original_descriptor_and_is_independent_of_model_order():
    records, evaluation, cfg, key, old, new, row = retest()
    evaluation = selection(evaluation, [row]); items = records + [old, new]
    report = assess(items, evaluation, cfg); expected = report.data
    assert assess(list(reversed(items)), evaluation, cfg).data == expected
    changed = evaluation.data; changed['replacements'] = []
    object.__setattr__(evaluation, '_encoded', canonical_json_bytes(changed))
    assert assess(items, evaluation, cfg).data == expected
    report.data['checks'].clear(); row['reason'] = 'Changed'; old['result'] = 'passed'
    assert report.data == expected and report.sha256 == canonical_json_sha256(expected)
    with pytest.raises(TypeError): bool(report)
    with pytest.raises(TypeError): VerificationReplacementAssessment()
    with pytest.raises(FrozenInstanceError): report._encoded = b'{}'


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_replacement_contract_is_identical_in_isolated_core_and_pyz(mode, tmp_path):
    records, evaluation, cfg, key, old, new, row = retest()
    evaluation = selection(evaluation, [row]); supplied = model(records + [old, new])
    expected = assess_run_replacements(supplied, evaluation, configuration_id=cfg).data
    body = '''import json
from specroad.changes import TargetModel
from specroad.verification import VerificationEvaluation, assess_run_replacements
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
print(json.dumps(assess_run_replacements(owned,evaluation,configuration_id=configuration_id).data))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
