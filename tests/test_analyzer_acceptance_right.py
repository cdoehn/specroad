"""Full original inputs and explicit non-successes through real worker pipes.

Boundary score rows are deliberate fault injection after the original model
load, not an accuracy corpus or a claim about the detector's predicted labels.
"""
import pytest

from specroad.analyzers.file_adapter import default_inputs
from specroad.analyzers.language_policy import execution_outcome
from support.analyzer_acceptance import invoke_case, native_request
from support import analyzer_acceptance
from support.read_only import inventory
from test_analyzer_acceptance import TEXT
from test_analyzer_reference import reference_request


runtime_factory = analyzer_acceptance.runtime_factory

@pytest.mark.parametrize('mode', ['missing_numpy', 'missing_py3langid', 'model:hash'])
def test_unavailable_real_backend_keeps_all_short_and_long_subjects(
        tmp_path, monkeypatch, runtime_factory, mode):
    request = native_request(tmp_path / 'project', [('en', TEXT), ('en', 'x'),
        ('en', ' \t' + 'x' * 19 + '\n'), ('en', TEXT + ' A second complete statement.')])
    before = inventory(tmp_path)
    package = invoke_case(monkeypatch, runtime_factory(), request, mode)
    report = package.reports[0].data
    assert report['run_status'] == 'partial'
    assert report['coverage']['counts'] == dict(expected=4, done=0, undetermined=2, failed=0, open=2)
    values = {s['subject_key']: s['value'] for s in request.data['subjects']}
    assert {s['subject_key'] for s in report['subjects']} == set(values)
    for subject in report['subjects']:
        decision = subject['payload']['specroad.language_detection']['decision']
        short = len(values[subject['subject_key']].strip(' \t\n')) < 20
        assert decision['status'] == ('undetermined' if short else 'unavailable')
        assert decision['reason'] == ('insufficient_text' if short else 'analyzer_model_unavailable')
        assert decision['language'] is None and decision['scores'] == []
    probe = report['operational']['test_probe']
    assert probe == dict(model_loads=0, model_load_attempts=1, ranked_value_hashes=[])
    assert report['engine']['model_sha256']['value'] is None
    outcome = execution_outcome(package.reports)
    assert outcome['exit_code'] == 5 and not outcome['execution_complete']
    assert not outcome['gate_passed'] and not outcome['all_languages_confirmed']
    assert package.request.canonical_bytes == request.canonical_bytes
    assert inventory(tmp_path) == before


def test_empty_transport_strings_need_no_optional_backend(monkeypatch, runtime_factory):
    # Empty statements are not legal native requirement records. The generic
    # request contract still accepts empty values; do not fake a project source.
    settings = default_inputs({})['settings']['specroad.py3langid']
    request = reference_request(['', ' \t\r\n\v\f', '123', 'x = 1;'], settings=settings)
    package = invoke_case(monkeypatch, runtime_factory(), request, 'missing_py3langid')
    report = package.reports[0].data
    assert report['coverage']['counts'] == dict(expected=4, done=0, undetermined=4, failed=0, open=0)
    assert report['operational']['test_probe'] == dict(
        model_loads=0, model_load_attempts=0, ranked_value_hashes=[])
    assert report['run_status'] == 'complete'
    assert all(s['payload']['specroad.language_detection']['decision']['reason'] == 'insufficient_text'
               for s in report['subjects'])
    outcome = execution_outcome(package.reports)
    assert outcome['exit_code'] == 0 and outcome['execution_complete']
    assert not outcome['all_languages_confirmed']
    assert package.request.canonical_bytes == request.canonical_bytes


def test_original_codepoints_and_long_tail_are_never_truncated(
        tmp_path, monkeypatch, runtime_factory):
    values = [' \t' + 'x' * 19 + '\n', ' \t' + 'x' * 20 + '\n',
              '\u00a0' + 'x' * 18 + '\u00a0', TEXT * 800 + ' e\u0301 日本語 FULL-END-MARKER']
    request = native_request(tmp_path / 'project', [('en', text) for text in values])
    before = inventory(tmp_path)
    package = invoke_case(monkeypatch, runtime_factory(), request)
    report = package.reports[0].data
    originals = {s['subject_key']: s for s in request.data['subjects']}
    ranked = [s['value_sha256'] for _, s in sorted(originals.items()) if s['value'] != values[0]]
    assert report['operational']['test_probe'] == dict(
        model_loads=1, model_load_attempts=1, ranked_value_hashes=ranked)
    assert report['run_status'] == 'complete'
    counts = report['coverage']['counts']
    assert counts['expected'] == counts['done'] + counts['undetermined'] == 4
    assert counts['failed'] == counts['open'] == 0
    for subject in report['subjects']:
        assert subject['value_sha256'] == originals[subject['subject_key']]['value_sha256']
        if originals[subject['subject_key']]['value'] == values[0]:
            assert subject['payload']['specroad.language_detection']['decision']['reason'] == 'insufficient_text'
    assert len(values[-1]) > 100000 and values[-1].endswith('FULL-END-MARKER')
    assert package.request.canonical_bytes == request.canonical_bytes
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('declared,label,status,resolution', [
    ('en', 'tie', None, None),
    ('cmn', 'zh', 'compatible_coarse', 'macrolanguage_only'),
    ('zh-Hant-TW', 'zh', 'compatible', 'primary_language'),
    ('en-GB', 'en', 'compatible', 'primary_language'),
    ('x-review', 'en', 'unverifiable', None),
    ('en', 'fr', 'mismatch', 'primary_language'),
])
def test_ties_and_primary_labels_do_not_invent_language_region_or_script_proof(
        tmp_path, monkeypatch, runtime_factory, declared, label, status, resolution):
    request = native_request(tmp_path / 'project', [(declared, TEXT)])
    before = inventory(tmp_path)
    package = invoke_case(monkeypatch, runtime_factory(), request, 'boundary:' + label)
    report = package.reports[0].data
    subject = report['subjects'][0]
    payload = subject['payload']['specroad.language_detection']
    decision, comparison = payload['decision'], payload['comparison']
    assert decision['score_semantics'] == 'normalized_uncalibrated_model_scores'
    if label == 'tie':
        assert decision['status'] == 'undetermined' and decision['language'] is None
        assert decision['reason'] == 'low_score_or_margin' and comparison is None
        assert decision['scores'] == [dict(language=code, score='0.500000000000') for code in ('en', 'fr')]
    else:
        assert decision['status'] == 'detected' and decision['language'] == label
        assert comparison['status'] == status and comparison['language_resolution'] == resolution
        assert comparison['region_checked'] is False and comparison['script_checked'] is False
        assert comparison['declared_language'] == declared
    assert report['coverage']['counts'] == dict(expected=1, done=int(label != 'tie'),
        undetermined=int(label == 'tie'), failed=0, open=0)
    assert report['operational']['test_probe'] == dict(model_loads=1, model_load_attempts=1,
        ranked_value_hashes=[request.data['subjects'][0]['value_sha256']])
    outcome = execution_outcome(package.reports)
    assert outcome['execution_complete'] and outcome['exit_code'] == 0
    assert outcome['all_languages_confirmed'] is (status == 'compatible')
    assert package.request.canonical_bytes == request.canonical_bytes
    assert inventory(tmp_path) == before
