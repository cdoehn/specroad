"""Independent action, observation and success oracles; no model-quality claim."""
from dataclasses import replace

import pytest

from specroad.analyzers._values import AnalyzerError
from specroad.analyzers.language_policy import assess_language, materialize_policy, execution_outcome
from specroad.analyzers.language_scores import LanguageDecision, SubjectDecision, ScoreDecision
from specroad.analyzers.requests import create_request
from specroad.storage.language_registry import bundled_language_registry
from test_analyzer_comparison import detected
from test_analyzer_text import language_request


def case(rows, **policy):
    request = language_request(['Independent complete original requirement.'] * len(rows), **policy)
    data = request.data
    for subject, (declared, _) in zip(data['subjects'], rows):
        subject['declared_language'] = declared
    request = create_request(**{k: data[k] for k in ('analyzers', 'subjects', 'context', 'settings', 'extensions')},
                             analysis_id=data['request_id'])
    values = tuple(SubjectDecision(s['subject_key'], s['value_sha256'], decision)
                   for s, (_, decision) in zip(request.data['subjects'], rows))
    p = request.data['settings']['specroad.py3langid']['language_detection']
    decisions = LanguageDecision(request.data['request_id'], request.data['snapshot_sha256'],
        request.data['analyzers'][0]['descriptor_sha256'], 'ascii-edge-codepoints-v1',
        p['min_text_codepoints'], p['min_score'], p['min_margin'], None, values)
    return request, decisions


def assess(request, decisions, **options):
    return assess_language(request, decisions, registry=bundled_language_registry(), **options)


def test_defaults_are_complete_owned_and_not_model_confidence():
    policy = materialize_policy()
    assert policy == dict(adapter='specroad.py3langid', adapter_version='1.0.0', mismatch='warning',
        undetermined='info', compatible_coarse='info', unverifiable='info', min_text_codepoints=20,
        min_score='0.900000000000', min_margin='0.100000000000')
    policy['undetermined'] = 'error'
    assert materialize_policy()['undetermined'] == 'info'


@pytest.mark.parametrize('action', ['mismatch', 'undetermined', 'compatible_coarse', 'unverifiable'])
@pytest.mark.parametrize('severity', ['ignore', 'info', 'warning', 'error'])
def test_materialized_action_space(action, severity):
    assert materialize_policy({action: severity})[action] == severity


def test_complete_info_nondecision_has_zero_exit_without_language_confirmation():
    request, decisions = case([('en', ScoreDecision('undetermined', 'low_score_or_margin', None, ()))])
    before = request.canonical_bytes
    value = assess(request, decisions)
    assert value.data == dict(execution_complete=True, all_languages_confirmed=False,
        findings_failed=False, gate_passed=True, exit_code=0)
    report = value.report.data
    assert report['run_status'] == 'complete'
    assert report['coverage']['counts'] == dict(expected=1, done=0, undetermined=1, failed=0, open=0)
    assert [f['severity'] for f in report['findings']] == ['info']
    assert report['subjects'][0]['payload']['specroad.language_detection']['decision']['reason'] == 'low_score_or_margin'
    assert request.canonical_bytes == before


def test_only_compatible_subjects_are_all_confirmed_without_region_or_script_claims():
    request, decisions = case([('en-US', detected('en')), ('de', detected('de'))])
    value = assess(request, decisions)
    assert value.data == dict(execution_complete=True, all_languages_confirmed=True,
        findings_failed=False, gate_passed=True, exit_code=0)
    assert value.report.data['findings'] == []
    for subject in value.report.data['subjects']:
        comparison = subject['payload']['specroad.language_detection']['comparison']
        assert comparison['region_checked'] is comparison['script_checked'] is False


def test_complete_report_copies_all_original_bindings_without_original_value():
    request, decisions = case([('en-IN', detected('fr')), ('cmn', detected('zh'))])
    original = {s['subject_key']: {k: v for k, v in s.items() if k != 'value'} for s in request.data['subjects']}
    value = assess(request, replace(decisions, subjects=tuple(reversed(decisions.subjects))))
    for subject in value.report.data['subjects']:
        assert {k: subject[k] for k in original[subject['subject_key']]} == original[subject['subject_key']]
        assert 'value' not in subject
    assert value.report.data['coverage']['counts']['done'] == 2
    assert not value.data['all_languages_confirmed']


def test_all_unknown_engine_facts_are_explicit_and_not_a_reproducibility_claim():
    request, decisions = case([('en', ScoreDecision('undetermined', 'insufficient_text', None, ()))])
    value = assess(request, decisions)
    assert all(f == {'value': None, 'reason': 'engine_not_loaded'}
               for k, f in value.report.data['engine'].items() if k != 'adapter_version')
    assert 'approval_granted' not in value.data and 'evidence' not in value.report.data


def test_invalid_fail_threshold_never_creates_success():
    request, decisions = case([('en', detected('en'))])
    with pytest.raises(AnalyzerError) as error:
        execution_outcome((assess(request, decisions).report,), fail_on='ignore')
    assert error.value.exit_code == 2
