"""Exact ASCII-edge length policy with full independent original strings."""
from dataclasses import FrozenInstanceError

import pytest

from specroad.analyzers._values import AnalyzerError
from specroad.analyzers.file_adapter import default_inputs
from specroad.analyzers.language_text import prepare_request
from support.processes import run_core
from test_analyzer_reference import controlled, reference_request


def language_request(texts, **overrides):
    settings = default_inputs({'analyzer_policy': {'language_detection': overrides}})['settings']
    return reference_request(texts, settings=settings['specroad.py3langid'])


@pytest.mark.parametrize('minimum', [1, 20, 10000])
def test_exact_minimum_is_inclusive_and_only_short_subjects_abstain(monkeypatch, minimum):
    calls, owners = controlled(monkeypatch)
    texts = ['x' * (minimum - 1), 'x' * minimum, 'x' * (minimum + 1)]
    request = language_request(texts, min_text_codepoints=minimum)
    result = prepare_request(request)
    originals = {s['subject_key']: s for s in request.data['subjects']}
    for item in result.subjects:
        short = len(originals[item.subject_key]['value']) < minimum
        assert (item.status, item.reason) == (('undetermined', 'insufficient_text')
                                             if short else ('ranked', None))
        assert len(item.scores) == (0 if short else 140)
    assert sorted(calls) == sorted(texts[1:])
    assert result.min_text_codepoints == minimum
    assert result.preprocessing_version == 'ascii-edge-codepoints-v1'
    assert len(owners) == 1 and owners[0]() is None


@pytest.mark.parametrize('edge', ['\t', '\n', '\v', '\f', '\r', ' ', ' \t\r\n\v\f'])
def test_ascii_edges_only_affect_length_not_the_original_backend_input(monkeypatch, edge):
    calls, _ = controlled(monkeypatch)
    request = language_request([edge + 'x' * 19 + edge, edge + 'x' * 20 + edge])
    result = prepare_request(request)
    assert calls == [edge + 'x' * 20 + edge]
    assert sorted(s.status for s in result.subjects) == ['ranked', 'undetermined']


@pytest.mark.parametrize('character', ['\u00a0', '\u2003', '\u2028', '\u202f', '\u3000', '\u200b', '\u0085', '\x1c', '😀', '界', '\u0301'])
def test_non_ascii_spaces_and_unicode_count_as_codepoints(monkeypatch, character):
    calls, _ = controlled(monkeypatch)
    text = character + 'x' * 19
    result = prepare_request(language_request([text]))
    assert calls == [text] and result.subjects[0].status == 'ranked'


def test_complete_independent_texts_and_original_hashes_are_preserved(monkeypatch):
    calls, owners = controlled(monkeypatch)
    texts = [' \tOriginal e\u0301 日本語 "quoted"\n' + 'long text ' * 4000 + ' unique tail  ',
             'execute("do not execute"); Arabic العربية and English\t', 'short']
    request = language_request(texts)
    original = request.canonical_bytes
    result = prepare_request(request)
    subjects = sorted(request.data['subjects'], key=lambda s: s['subject_key'])
    assert calls == [s['value'] for s in subjects if s['value'] != 'short']
    assert request.canonical_bytes == original
    assert [(s.subject_key, s.value_sha256) for s in result.subjects] == [
        (s['subject_key'], s['value_sha256']) for s in subjects]
    assert (result.request_id, result.snapshot_sha256, result.descriptor_sha256) == (
        request.data['request_id'], request.data['snapshot_sha256'],
        request.data['analyzers'][0]['descriptor_sha256'])
    assert len(owners) == 1 and owners[0]() is None
    assert result.engine.unicode_version and ('py3langid', '0.4.0') in result.engine.library_versions
    with pytest.raises(FrozenInstanceError):
        result.subjects[0].status = 'detected'


def test_all_short_values_need_no_model_and_still_have_full_request_bindings(monkeypatch):
    def forbidden():
        raise AssertionError('short text must not load an optional model')
    monkeypatch.setattr('specroad.analyzers._model_session.load_reference_model', forbidden)
    request = language_request(['', ' \n\t', 'x' * 19])
    result = prepare_request(request)
    assert result.engine is None and len(result.subjects) == 3
    assert all((s.status, s.reason, s.scores) == ('undetermined', 'insufficient_text', ())
               for s in result.subjects)
    assert result.snapshot_sha256 == request.data['snapshot_sha256']


@pytest.mark.parametrize('minimum', [0, 10001, -1, True, False, 20.0, '20', None])
def test_invalid_minimum_is_rejected_before_model_loading(monkeypatch, minimum):
    calls, owners = controlled(monkeypatch)
    with pytest.raises(AnalyzerError, match='min_text_codepoints') as caught:
        prepare_request(language_request(['long text ' * 5], min_text_codepoints=minimum))
    assert caught.value.exit_code == 2 and calls == owners == []


@pytest.mark.parametrize('settings', [{}, {'language_detection': {}}, {'languages': ['de']}])
def test_decision_path_requires_materialized_settings_without_candidate_filters(monkeypatch, settings):
    calls, owners = controlled(monkeypatch)
    with pytest.raises(AnalyzerError) as caught:
        prepare_request(reference_request(['long text ' * 5], settings=settings))
    assert caught.value.exit_code == 2 and calls == owners == []


@pytest.mark.parametrize('value', [None, 42, [], {}, True])
def test_any_wrong_subject_type_rejects_the_request_before_loading(monkeypatch, value):
    calls, owners = controlled(monkeypatch)
    with pytest.raises(AnalyzerError, match='text_subject_required') as caught:
        prepare_request(language_request(['otherwise valid text ' * 5, value]))
    assert caught.value.exit_code == 3 and calls == owners == []


def test_changed_length_policy_is_materialized_in_the_request_snapshot(monkeypatch):
    controlled(monkeypatch)
    left = language_request(['x' * 19])
    right = language_request(['x' * 19], min_text_codepoints=19)
    assert left.data['snapshot_sha256'] != right.data['snapshot_sha256']
    assert left.data['subjects'] == right.data['subjects']
    assert prepare_request(left).subjects[0].reason == 'insufficient_text'
    assert prepare_request(right).subjects[0].status == 'ranked'


def test_length_policy_import_is_passive_without_optional_dependencies(tmp_path):
    result = run_core('''
class RejectOptional:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('numpy', 'py3langid'):
            raise AssertionError('implicit model dependency')
sys.meta_path.insert(0, RejectOptional())
from specroad.analyzers.language_text import prepare_request
from specroad.analyzers.file_adapter import default_inputs
assert default_inputs({})['settings']['specroad.py3langid']['language_detection']['min_text_codepoints'] == 20
assert 'numpy' not in sys.modules and 'py3langid' not in sys.modules
''', tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
