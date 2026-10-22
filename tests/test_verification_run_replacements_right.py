"""Replacement chains cannot hide changed, foreign, incomplete or stale runs."""
from hashlib import sha256
import json

import pytest

from specroad.changes import TargetModel
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.validation import ModelDocument
from specroad.verification import (VerificationEvaluation, VerificationEvaluationError,
    VerificationReplacementAuthorityError, assess_run_replacements)
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.records import ref
from support.targets import model
from test_verification_evaluation import ACTOR
from test_verification_required_checks import edge
from test_verification_required_checks_right import bindings_for, scope
from test_verification_run_selection import case, observation
from test_verification_run_replacements import retest, selection, decision, assess, check


def replacement(data, old='ci:old'):
    return next(row for row in check(data)['replacements'] if row['decision']['replaced_run_id'] == old)


@pytest.mark.parametrize('actor_type', ['ai', 'ci', 'tool'])
def test_nonhuman_authority_is_refused_even_with_human_creator_and_current_failed_retest(actor_type):
    records, evaluation, cfg, key, old, new, row = retest()
    new['result'] = 'failed'
    data = evaluation.data; data['created_by'] = ACTOR
    data['replacements'] = [{**row, 'authorized_by': {'actor_type': actor_type, 'actor_id': 'declared'}}]
    supplied = model(records + [old, new]); before = supplied.source_files
    # Forging the cached canonical value cannot bypass re-reading original bytes.
    object.__setattr__(evaluation, 'source_bytes', artifact_bytes(data))
    with no_write_attempts(), pytest.raises(VerificationReplacementAuthorityError) as caught:
        assess_run_replacements(supplied, evaluation, configuration_id=cfg)
    assert caught.value.exit_code == 7 and caught.value.code == 'SRV175'
    assert caught.value.pointer == '/replacements/0/authorized_by'
    assert supplied.source_files == before and old['result'] == new['result'] == 'failed'


def test_ai_may_record_an_explicit_human_decision_without_authenticating_it():
    records, evaluation, cfg, key, old, new, row = retest()
    value = evaluation.data; value['created_by'] = {'actor_type': 'ai', 'actor_id': 'recorder'}
    value['replacements'] = [row]; value['evaluation_id'] = 'EVAL-' + '0' * 25 + '3'
    data = assess(records + [old, new], VerificationEvaluation(artifact_bytes(value)), cfg).data
    assert replacement(data)['effective'] and not data['human_identity_authenticated']
    assert replacement(data)['decision']['authorized_by'] == ACTOR


@pytest.mark.parametrize('field,value', [
    ('authorized_at', '2026-02-30T12:00:00Z'), ('authorized_at', '2026-10-21T12:00:00+01:00'),
    ('authorized_at', 'whenever done'), ('authorized_by', {'actor_type': 'human', 'actor_id': ' '}),
    ('authorized_by', {'actor_type': 'human', 'actor_id': 'reviewer', 'verified': True}),
    ('reason', '\u0000'), ('replacement_run_ids', None), ('replaced_evidence_set_sha256', 'A' * 64)])
def test_invalid_authority_metadata_and_binding_values_remain_structured_input_errors(field, value):
    _, evaluation, _, _, _, _, row = retest(); row[field] = value
    with pytest.raises(VerificationEvaluationError) as caught:
        selection(evaluation, [row])
    assert caught.value.code == 'SRV175' and caught.value.exit_code == 3
    assert caught.value.pointer.startswith('/replacements')


@pytest.mark.parametrize('field', ['replaced_run_id', 'replacement_run_ids'])
@pytest.mark.parametrize('bad_id', [':local', 'producer:', ' :local', 'producer: ', 'producer:local '])
def test_neither_old_nor_replacement_run_can_gain_an_inferred_namespace(field, bad_id):
    _, evaluation, _, _, _, _, row = retest()
    row[field] = [bad_id] if field == 'replacement_run_ids' else bad_id
    with pytest.raises(VerificationEvaluationError) as caught:
        selection(evaluation, [row])
    assert caught.value.exit_code == 3 and caught.value.reason == 'namespaced_replacement_run_id_required'


@pytest.mark.parametrize('reverse', [False, True])
def test_cycle_in_a_branch_is_rejected_even_beside_a_current_success(reverse):
    _, evaluation, _, key, old, new, row = retest()
    rows = [decision(key, 'ci:old', [old], ('ci:new', 'ci:good')),
            decision(key, 'ci:new', [new], ('ci:third',)),
            decision(key, 'ci:third', [new], ('ci:old',))]
    if reverse: rows.reverse()
    with pytest.raises(VerificationEvaluationError) as caught:
        selection(evaluation, rows)
    assert caught.value.code == 'SRV175' and caught.value.reason == 'cyclic_run_replacement'


@pytest.mark.parametrize('cyclic', [False, True])
def test_long_flat_replacement_graph_does_not_depend_on_python_recursion_depth(cyclic):
    _, evaluation, _, _, _, _, row = retest()
    rows = [{**row, 'replaced_run_id': f'ci:{n}', 'replacement_run_ids': [f'ci:{n+1}']}
            for n in range(1100)]
    if cyclic:
        rows[-1]['replacement_run_ids'] = ['ci:0']
        with pytest.raises(VerificationEvaluationError) as caught: selection(evaluation, rows)
        assert caught.value.reason == 'cyclic_run_replacement'
    else:
        result = selection(evaluation, rows)
        assert len(result.data['replacements']) == 1100
        assert result.state_sha256 == evaluation.state_sha256


@pytest.mark.parametrize('field,value', [('result', 'passed'), ('revision', 2),
    ('updated_at', '2026-10-21T01:00:00Z'), ('producer', {'producer_type': 'ci', 'producer_id': 'another'}),
    ('environment', {'platform': 'different'}), ('tags', ['later-known'])])
def test_full_artifact_change_invalidates_old_set_even_if_run_and_context_hashes_match(field, value):
    records, evaluation, cfg, key, old, new, row = retest()
    old[field] = value
    data = assess(records + [old, new], selection(evaluation, [row]), cfg).data
    item = replacement(data)
    assert item['old_run_observed'] and not item['evidence_set_matches'] and not item['effective']
    assert item['binding_issues'] == [{'run_id': 'ci:old', 'reason': 'replaced_evidence_set_changed'}]
    assert 'ci:old' in check(data)['active_run_ids'] and data['verification_result'] == 'incomplete'


@pytest.mark.parametrize('change', ['configuration', 'policy', 'missing_policy'])
def test_matching_set_hash_does_not_substitute_an_old_run_without_admissible_configuration(change):
    records, evaluation, cfg, key, old, new, row = retest()
    if change == 'configuration': old['configuration_hash'] = 'f' * 64
    if change == 'policy': old['configuration_policy'] = 'independent'
    if change == 'missing_policy': del old['configuration_policy']
    row = decision(key, 'ci:old', [old])
    data = assess(records + [old, new], selection(evaluation, [row]), cfg).data
    item = replacement(data)
    assert item['evidence_set_matches'] and not item['old_run_observed'] and not item['effective']
    assert item['binding_issues'] == [{'run_id': 'ci:old', 'reason': 'replaced_run_missing'}]
    assert data['missing_runs'] == [{**key, 'run_id': 'ci:old'}]
    assert check(data)['effective_expected_run_ids'] == ['ci:old']
    assert data['verification_result'] == 'incomplete'


@pytest.mark.parametrize('change', ['product', 'state', 'slot', 'subject', 'test', 'configuration'])
def test_foreign_replacement_evidence_cannot_witness_a_terminal_of_this_key_and_product(change):
    records, evaluation, cfg, key, old, new, row = retest()
    if change == 'product': new['run_context']['subject_id'] = 'other-product'
    if change == 'state': new['run_context']['subject_state_sha256'] = 'a' * 64
    if change == 'slot': new['run_context']['check_id'] = 'other'
    if change == 'subject': new['subjects'] = [s for s in new['subjects'] if s['artifact_id'] != key['subject_artifact_id']]
    if change == 'test': new['run_context']['test_id'] = ref('TEST')
    if change == 'configuration': new['configuration_hash'] = 'f' * 64
    data = assess(records + [old, new], selection(evaluation, [row]), cfg).data
    item = replacement(data); terminal = item['terminal_runs'][0]
    assert not item['effective'] and item['old_run_observed']
    assert terminal == {'run_id': 'ci:new', 'presence': 'missing', 'current_complete': False,
                        'reasons': ['replacement_run_missing'], 'evidence': []}
    assert check(data)['active_run_ids'] == ['ci:old'] and data['verification_result'] == 'incomplete'


@pytest.mark.parametrize('result,freshness,complete,reasons', [
    ('failed', 'current', True, []), ('passed', 'current', True, []),
    ('running', 'current', False, ['replacement_run_incomplete']),
    ('not_measured', 'current', False, ['replacement_run_incomplete']),
    ('failed', 'stale', False, ['replacement_run_not_current']),
    ('passed', 'stale', False, ['replacement_run_not_current']),
    ('running', 'stale', False, ['replacement_run_not_current', 'replacement_run_incomplete'])])
def test_terminal_report_preserves_every_raw_result_and_all_binding_defects(result, freshness, complete, reasons):
    records, evaluation, cfg, key, old, new, row = retest()
    new['result'] = result
    if freshness == 'stale': new['subjects'][0]['verification_context_sha256'] = 'f' * 64
    data = assess(records + [old, new], selection(evaluation, [row]), cfg).data
    item = replacement(data); terminal = item['terminal_runs'][0]
    assert terminal['presence'] == 'present' and terminal['current_complete'] is complete
    assert terminal['reasons'] == reasons and item['effective'] is complete
    assert terminal['evidence'] == [{'evidence_id': new['id'], 'result': result, 'freshness': freshness,
        'artifact_sha256': canonical_json_sha256(new), 'source_sha256': sha256(canonical_json_bytes(new)).hexdigest()}]
    assert data['verification_result'] == (None if complete else 'incomplete')
    assert not data['result_aggregation_evaluated']


def test_one_complete_failed_observation_does_not_hide_an_incomplete_observation_of_its_terminal():
    records, evaluation, cfg, key, old, new, row = retest(); new['result'] = 'failed'
    extra = observation(records, evaluation, key, token='3', run='ci:new', result='running')
    data = assess(records + [old, new, extra], selection(evaluation, [row]), cfg).data
    item = replacement(data)
    assert not item['effective'] and data['verification_result'] == 'incomplete'
    assert [e['result'] for e in item['terminal_runs'][0]['evidence']] == ['failed', 'running']
    assert item['terminal_runs'][0]['reasons'] == ['replacement_run_incomplete']


@pytest.mark.parametrize('change', ['extra_evidence', 'excluded_configuration'])
def test_broken_intermediate_binding_invalidates_all_ancestors_not_only_direct_decision(change):
    records, evaluation, cfg, key, old, middle, row = retest()
    terminal = observation(records, evaluation, key, token='3', run='ci:terminal', result='failed')
    if change == 'excluded_configuration': middle['configuration_hash'] = 'f' * 64
    middle_row = decision(key, 'ci:new', [middle], ('ci:terminal',))
    items = [old, middle, terminal]
    if change == 'extra_evidence': items.append(observation(records, evaluation, key, token='4', run='ci:new'))
    data = assess(records + items, selection(evaluation, [row, middle_row]), cfg).data
    for run_id in ('ci:old', 'ci:new'):
        item = replacement(data, run_id)
        assert not item['effective'] and item['terminal_runs'][0]['current_complete']
        assert item['binding_issues'] == [{'run_id': 'ci:new', 'reason': (
            'replaced_evidence_set_changed' if change == 'extra_evidence' else 'replaced_run_missing')}]
    assert check(data)['superseded_run_ids'] == [] and data['verification_result'] == 'incomplete'


def test_stale_intermediate_can_be_replaced_when_its_own_binding_and_terminal_are_valid():
    records, evaluation, cfg, key, old, middle, row = retest()
    middle['subjects'][0]['verification_context_sha256'] = 'f' * 64
    terminal = observation(records, evaluation, key, token='3', run='ci:terminal', result='failed')
    middle_row = decision(key, 'ci:new', [middle], ('ci:terminal',))
    data = assess(records + [old, middle, terminal], selection(evaluation, [row, middle_row]), cfg).data
    assert check(data)['superseded_run_ids'] == ['ci:new', 'ci:old']
    assert check(data)['active_run_ids'] == check(data)['effective_expected_run_ids'] == ['ci:terminal']
    assert replacement(data)['terminal_runs'][0]['evidence'][0]['result'] == 'failed'
    assert data['verification_result'] is None


def test_diamond_graph_deduplicates_shared_terminal_and_preserves_missing_unrelated_expectation():
    records, evaluation, cfg, key, old, middle, row = retest(expected=('ci:old', 'ci:unrelated'))
    other = observation(records, evaluation, key, token='3', run='ci:branch')
    terminal = observation(records, evaluation, key, token='4', run='ci:end', result='failed')
    rows = [decision(key, 'ci:old', [old], ('ci:new', 'ci:branch')),
            decision(key, 'ci:new', [middle], ('ci:end',)),
            decision(key, 'ci:branch', [other], ('ci:end',))]
    data = assess(records + [old, middle, other, terminal], selection(evaluation, rows), cfg).data
    assert len(replacement(data)['terminal_runs']) == 1
    assert check(data)['active_run_ids'] == check(data)['effective_expected_run_ids'] == ['ci:end', 'ci:unrelated']
    assert data['missing_runs'] == [{**key, 'run_id': 'ci:unrelated'}]
    assert data['diagnostics'] == [{'code': 'SRV176', 'severity': 'warning', 'reason': 'required_run_missing', **key, 'run_id': 'ci:unrelated'}]


def test_one_bad_branch_prevents_parent_replacement_without_undoing_independent_valid_decision():
    records, evaluation, cfg, key, old, new, row = retest()
    other = observation(records, evaluation, key, token='3', run='ci:other')
    rows = [decision(key, 'ci:old', [old], ('ci:new', 'ci:missing')),
            decision(key, 'ci:other', [other], ('ci:new',))]
    data = assess(records + [old, new, other], selection(evaluation, rows), cfg).data
    assert not replacement(data)['effective'] and replacement(data, 'ci:other')['effective']
    assert check(data)['superseded_run_ids'] == ['ci:other']
    assert check(data)['active_run_ids'] == ['ci:new', 'ci:old']
    assert data['verification_result'] == 'incomplete'


def test_new_old_evidence_requires_a_new_explicit_complete_decision_and_keeps_originals():
    records, evaluation, cfg, key, old, new, row = retest()
    first = selection(evaluation, [row])
    extra = observation(records, evaluation, key, token='3', run='ci:old')
    supplied = model(records + [old, new, extra]); before = supplied.source_files
    with no_write_attempts():
        rejected = assess_run_replacements(supplied, first, configuration_id=cfg)
        value = first.data; value['evaluation_id'] = 'EVAL-' + '0' * 25 + '3'
        value['replacements'] = [decision(key, 'ci:old', [extra, old])]
        second = VerificationEvaluation(artifact_bytes(value))
        accepted = assess_run_replacements(supplied, second, configuration_id=cfg)
    assert rejected.data['verification_result'] == 'incomplete' and not replacement(rejected.data)['effective']
    assert replacement(accepted.data)['effective'] and accepted.data['verification_result'] is None
    assert first.sha256 != second.sha256 and first.state_sha256 == second.state_sha256
    assert supplied.source_files == before and old['result'] == extra['result'] == 'failed'


def test_original_evidence_encoding_is_preserved_and_full_artifact_hash_is_canonical():
    records, evaluation, cfg, key, old, new, row = retest()
    supplied = model(records + [old, new]); documents = []
    for d in supplied.documents:
        raw = json.dumps(json.loads(d.content), indent=4, ensure_ascii=False).encode() + b'\n'
        documents.append(ModelDocument(d.path, raw))
    supplied = TargetModel(supplied.configuration_bytes, supplied.binding, documents,
        profile=supplied.profile, resource_files=supplied.resource_files)
    before = supplied.source_files
    with no_write_attempts(): data = assess_run_replacements(supplied, selection(evaluation, [row]), configuration_id=cfg).data
    assert replacement(data)['effective'] and replacement(data)['evidence_set'][0]['sha256'] == canonical_json_sha256(old)
    terminal = replacement(data)['terminal_runs'][0]['evidence'][0]
    assert terminal['source_sha256'] != terminal['artifact_sha256']
    assert terminal['source_sha256'] in {sha256(raw).hexdigest() for raw in before.values()}
    assert supplied.source_files == before


def test_explicit_native_scope_does_not_gain_obligations_from_replacement_metadata():
    records, evaluation, cfg, key, old, new, row = retest()
    records.append(domain_value('requirement', id=ref('REQ', '3')))
    supplied = model(records + [old, new]); evaluation = selection(evaluation, [row])
    data = assess_run_replacements(supplied, evaluation, configuration_id=cfg,
        scope_descriptor=scope(ref(), configuration_id=cfg), scope_bindings=bindings_for(supplied)).data
    assert len(data['checks']) == 1 and replacement(data)['effective']
    assert not data['project_required_checks_complete']


def test_shared_old_run_is_replaced_only_for_the_explicitly_authorized_subject():
    records, evaluation, cfg, key = case(expected=('ci:old',))
    other = domain_value('requirement', id=ref('REQ', '2'), relations=[edge(ref('VER'), 1)])
    records.append(other); records[1]['subjects'].append(other['id'])
    other_key = {**key, 'subject_artifact_id': other['id']}
    value = evaluation.data; value['required_runs'].append({**other_key, 'run_ids': ['ci:old']})
    evaluation = VerificationEvaluation(artifact_bytes(value))
    old = observation(records, evaluation, key, run='ci:old')
    other_old = observation(records, evaluation, other_key, token='3', run='ci:old')
    old['subjects'].append(next(s for s in other_old['subjects'] if s['artifact_id'] == other['id']))
    new = observation(records, evaluation, key, token='2', run='ci:new', result='passed')
    data = assess(records + [old, new], selection(evaluation, [decision(key, 'ci:old', [old])]), cfg).data
    assert data['checks'][0]['superseded_run_ids'] == ['ci:old']
    assert data['checks'][1]['superseded_run_ids'] == [] and data['checks'][1]['active_run_ids'] == ['ci:old']


@pytest.mark.parametrize('kind', ['capability', 'task'])
def test_unsupported_terminal_context_never_becomes_current_from_matching_audit_hash(kind):
    records, evaluation, cfg, key = case(direct=True, subject_kind=kind, expected=('ci:old',))
    old = observation(records, evaluation, key, run='ci:old')
    new = observation(records, evaluation, key, token='2', run='ci:new', result='passed')
    # The formerly unsupported subject's stored placeholder is still stale;
    # matching audit hashes do not replace the now-defined Appendix L binding.
    next(s for s in new['subjects'] if s['artifact_id'] == key['subject_artifact_id'])[
        'verification_context_sha256'] = 'a' * 64
    data = assess(records + [old, new], selection(evaluation, [decision(key, 'ci:old', [old])]), cfg).data
    item = replacement(data)
    assert not item['effective'] and item['terminal_runs'][0]['reasons'] == ['replacement_run_not_current']
    assert item['terminal_runs'][0]['evidence'][0]['freshness'] == 'stale'
    assert data['verification_result'] == 'incomplete'


def test_conflicting_product_identity_of_one_run_is_not_downgraded_to_missing_replacement():
    records, evaluation, cfg, key, old, new, row = retest()
    another = observation(records, evaluation, key, token='3', run='ci:new')
    another['run_context']['subject_state_sha256'] = 'f' * 64
    with pytest.raises(ModelError) as caught:
        assess(records + [old, new, another], selection(evaluation, [row]), cfg)
    assert caught.value.reason == 'evidence_run_identity_conflict'


def test_terminal_report_owns_nested_results_and_is_invariant_under_input_order():
    records, evaluation, cfg, key, old, new, row = retest()
    evaluation = selection(evaluation, [row]); items = records + [old, new]
    report = assess(items, evaluation, cfg); original = report.data
    assert assess(items[::-1], evaluation, cfg).data == original
    replacement(report.data)['terminal_runs'][0]['evidence'].clear()
    new['result'] = 'failed'; row['replacement_run_ids'].append('ci:invented')
    assert report.data == original and report.sha256 == canonical_json_sha256(original)


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_complete_failure_and_invalid_chain_bindings_match_in_isolated_core_and_pyz(mode, tmp_path):
    records, evaluation, cfg, key, old, new, row = retest(); new['result'] = 'failed'
    row['replacement_run_ids'].append('ci:absent')
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
