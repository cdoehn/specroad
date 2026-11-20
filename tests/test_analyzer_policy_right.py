"""Technical failures cannot be downgraded; ignored observations stay covered."""
from dataclasses import replace

import pytest

from specroad.analyzers._values import AnalyzerError, encoded
from specroad.analyzers.language_policy import execution_outcome, materialize_policy
from specroad.analyzers.language_scores import ScoreDecision
from specroad.analyzers.packages import create_package
from specroad.analyzers.reports import create_report, subject_result
from specroad.analyzers.worker import analyze_language
from specroad.cli.application import dispatch_result
from specroad.cli.results import thaw
from test_analyzer_comparison import detected
from test_analyzer_policy import case, assess


@pytest.mark.parametrize('action', ['mismatch', 'undetermined', 'compatible_coarse', 'unverifiable'])
@pytest.mark.parametrize('value', [None, False, 0, [], {}, 'fatal'])
def test_invalid_actions_fail_as_usage_before_optional_loading(action, value, monkeypatch):
    monkeypatch.setattr('specroad.analyzers._model_session.load_reference_model',
        lambda: pytest.fail('policy error reached model'))
    with pytest.raises(AnalyzerError) as caught:
        materialize_policy({action: value})
    assert caught.value.exit_code == 2


@pytest.mark.parametrize('status,run_status', [('unavailable', 'unavailable'), ('failed', 'failed')])
def test_technical_failure_retains_code_five_even_when_every_finding_is_ignored(status, run_status):
    request, decisions = case([('en', ScoreDecision(status, 'backend_error', None, ()))],
        mismatch='ignore', undetermined='ignore', compatible_coarse='ignore', unverifiable='ignore')
    value = assess(request, decisions)
    assert value.data == dict(execution_complete=False, all_languages_confirmed=False,
        findings_failed=False, gate_passed=False, exit_code=5)
    assert value.report.data['run_status'] == run_status and value.report.data['findings'] == []
    assert value.report.data['coverage']['counts']['expected'] == 1


@pytest.mark.parametrize('severity,fail_on,exit_code', [('info', 'warning', 0), ('warning', 'warning', 1),
    ('warning', 'error', 0), ('error', 'warning', 1), ('error', 'error', 1), ('ignore', 'warning', 0)])
def test_exact_fail_threshold_is_independent_of_language_confirmation(severity, fail_on, exit_code):
    request, decisions = case([('en', detected('fr'))], mismatch=severity)
    value = assess(request, decisions, fail_on=fail_on)
    assert value.data == dict(execution_complete=True, all_languages_confirmed=False,
        findings_failed=exit_code == 1, gate_passed=exit_code == 0, exit_code=exit_code)


@pytest.mark.parametrize('declared,decision,action', [('cmn', detected('zh'), 'compatible_coarse'),
    ('x-company', detected('en'), 'unverifiable'), ('en', detected('fr'), 'mismatch'),
    ('en', ScoreDecision('undetermined', 'low_score_or_margin', None, ()), 'undetermined')])
def test_ignore_removes_only_findings_and_never_observation_or_coverage(declared, decision, action):
    req, dec = case([(declared, decision)])
    ignored_req, ignored_dec = case([(declared, decision)], **{action: 'ignore'})
    normal, ignored = assess(req, dec).report.data, assess(ignored_req, ignored_dec).report.data
    assert normal['coverage'] == ignored['coverage'] and normal['run_status'] == ignored['run_status']
    assert normal['subjects'][0]['payload'] == ignored['subjects'][0]['payload']
    assert len(normal['findings']) == 1 and ignored['findings'] == []
    assert not assess(ignored_req, ignored_dec).data['all_languages_confirmed']


def test_technical_failure_wins_over_business_failure_and_retains_every_subject():
    request, decisions = case([('en', detected('fr')), ('en', ScoreDecision('unavailable', 'missing', None, ())),
        ('en', ScoreDecision('undetermined', 'insufficient_text', None, ()))], mismatch='error')
    value = assess(request, decisions)
    assert value.data['exit_code'] == 5 and value.data['findings_failed']
    assert value.report.data['run_status'] == 'partial'
    assert value.report.data['coverage']['counts'] == dict(expected=3, done=1, undetermined=1, failed=0, open=1)


def test_changed_request_and_duplicate_decisions_are_not_accepted():
    request, decisions = case([('en', detected('en'))])
    for invalid in (replace(decisions, snapshot_sha256='a' * 64),
                    replace(decisions, subjects=decisions.subjects * 2)):
        with pytest.raises(AnalyzerError) as error:
            assess(request, invalid)
        assert error.value.exit_code == 6


def test_opaque_complete_payload_never_claims_language_confirmation():
    request, decisions = case([('en', detected('en'))])
    engine = assess(request, decisions).report.data['engine']
    for payload in ({}, {'specroad.language_detection': None},
                    {'specroad.language_detection': {'comparison': {'status': 'compatible'}}}):
        report = create_report(request, analyzer_id='specroad.py3langid', engine=engine,
            run_status='complete', subjects=[subject_result(request.data['subjects'][0], status='done', payload=payload)])
        assert execution_outcome((report,))['execution_complete'] is True
        assert execution_outcome((report,))['all_languages_confirmed'] is False


def test_worker_rejects_threshold_before_loading(monkeypatch):
    request, _ = case([('en', detected('en'))])
    monkeypatch.setattr('specroad.analyzers._model_session.load_reference_model',
        lambda: pytest.fail('invalid fail threshold initialized model'))
    with pytest.raises(AnalyzerError) as error:
        analyze_language(request, fail_on='ignore')
    assert error.value.exit_code == 2


@pytest.mark.parametrize('severity,fail_on,expected', [('info', 'warning', 0),
    ('warning', 'warning', 1), ('error', 'error', 1)])
def test_cli_run_uses_the_report_outcome_instead_of_a_fixed_exit(tmp_path, monkeypatch, severity, fail_on, expected):
    request, decisions = case([('en', detected('fr'))], mismatch=severity)
    report = assess(request, decisions).report
    package = create_package(request, [report])
    (tmp_path / 'request.json').write_bytes(request.canonical_bytes)
    monkeypatch.setattr('specroad.cli.analyzer_cli.execute', lambda supplied: package
        if supplied.canonical_bytes == request.canonical_bytes else pytest.fail('request binding changed'))
    result = dispatch_result(['analyzer', 'run', '--request', 'request.json', '--fail-on', fail_on], cwd=tmp_path)
    assert result.exit_code == expected and result.details['execution_complete'] is True
    assert result.details['all_languages_confirmed'] is False
    assert result.details['gate_passed'] is (expected == 0)
    assert (tmp_path / 'request.json').read_bytes() == request.canonical_bytes
    assert encoded(thaw(result.result)) == package.canonical_bytes
