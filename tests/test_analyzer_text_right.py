"""Unicode ownership and explicit per-subject outcomes at backend boundaries."""
import sys
import unicodedata

import pytest

from specroad.analyzers._values import AnalyzerError
from specroad.analyzers.language_text import prepare_request
from test_analyzer_reference import ControlledModel, controlled
from test_analyzer_text import language_request


@pytest.mark.parametrize('reason', ['analyzer_model_unavailable', 'analyzer_model_hash', 'analyzer_library_version'])
def test_unavailable_model_is_attempted_once_and_short_text_keeps_precedence(monkeypatch, reason):
    attempts = []
    def unavailable():
        attempts.append(True)
        raise AnalyzerError(reason, exit_code=5)
    monkeypatch.setattr('specroad.analyzers._model_session.load_reference_model', unavailable)
    request = language_request(['long original text ' * 3, '', 'another original text ' * 3])
    result = prepare_request(request)
    originals = {s['subject_key']: s['value'] for s in request.data['subjects']}
    assert attempts == [True] and result.engine is None
    for subject in result.subjects:
        assert (subject.status, subject.reason, subject.scores) == (
            ('unavailable', reason, ()) if originals[subject.subject_key] else
            ('undetermined', 'insufficient_text', ()))


def test_unbound_library_version_cannot_publish_a_ranked_subject(monkeypatch):
    calls, owners = controlled(monkeypatch)
    monkeypatch.delattr(sys.modules['py3langid'], '__version__')
    result = prepare_request(language_request(['long original value ' * 3, 'second long value ' * 3]))
    assert calls == [] and len(owners) == 1 and owners[0]() is None
    assert result.engine is None
    assert all(s.status == 'unavailable' and not s.scores for s in result.subjects)


def test_invalid_subject_rank_does_not_hide_other_independent_subjects(monkeypatch):
    calls, _ = controlled(monkeypatch)
    original_rank = ControlledModel.rank
    def rank(self, text):
        if text.startswith('broken'):
            calls.append(text)
            return [('en', float('nan'))]
        return original_rank(self, text)
    monkeypatch.setattr(ControlledModel, 'rank', rank)
    request = language_request(['broken output for this text', 'valid independent full input', 'x'])
    result = prepare_request(request)
    originals = {s['subject_key']: s['value'] for s in request.data['subjects']}
    for subject in result.subjects:
        text = originals[subject.subject_key]
        if text.startswith('broken'):
            assert (subject.status, subject.reason, subject.scores) == ('failed', 'invalid_backend_output', ())
        elif text == 'x':
            assert (subject.status, subject.reason) == ('undetermined', 'insufficient_text')
        else:
            assert subject.status == 'ranked' and len(subject.scores) == 140
    assert sorted(calls) == sorted(t for t in originals.values() if t != 'x')


@pytest.mark.parametrize('change', [('labels', ['en']), ('_norm_probs', False), ('min_confidence', 0.9)])
def test_wrong_model_contract_is_unavailable_without_false_language_claim(monkeypatch, change):
    calls, owners = controlled(monkeypatch, change=change)
    result = prepare_request(language_request(['first complete original text', 'another complete original text']))
    assert calls == [] and len(owners) == 1
    assert all((s.status, s.reason, s.scores) == ('unavailable', 'analyzer_reference_model_state', ())
               for s in result.subjects)


@pytest.mark.parametrize('error', [KeyboardInterrupt, SystemExit, MemoryError])
def test_process_and_resource_failures_are_not_disguised_as_abstention(monkeypatch, error):
    controlled(monkeypatch)
    def fail(self, text):
        raise error('controlled process boundary')
    monkeypatch.setattr(ControlledModel, 'rank', fail)
    with pytest.raises(error):
        prepare_request(language_request(['original complete text ' * 3]))


def test_backend_working_copy_never_replaces_original_unicode_hash_or_declared_language(monkeypatch):
    calls, _ = controlled(monkeypatch)
    original_rank = ControlledModel.rank
    working = []
    def normalize(self, text):
        working.append(unicodedata.normalize('NFC', text).upper())
        return original_rank(self, text)
    monkeypatch.setattr(ControlledModel, 'rank', normalize)
    texts = ['e\u0301cole "German quote" 日本語\ncode(); العربية' * 3,
             'école "German quote" 日本語\ncode(); العربية' * 3]
    request = language_request(texts)
    before = request.canonical_bytes
    result = prepare_request(request)
    assert working[0] == working[1] and len(set(calls)) == 2
    assert len({s.value_sha256 for s in result.subjects}) == 2
    assert request.canonical_bytes == before
    assert all(s['declared_language'] == 'de' for s in request.data['subjects'])
    assert result.engine.unicode_version == unicodedata.unidata_version


def test_ascii_inside_the_string_is_neither_removed_nor_segmented(monkeypatch):
    calls, _ = controlled(monkeypatch)
    text = 'x' + '\t\n\r\v\f ' * 3 + 'x'
    result = prepare_request(language_request([text]))
    assert len(text) == 20 and calls == [text] and result.subjects[0].status == 'ranked'
