"""Published fixed decimals are the only basis of the exact score decision."""
from dataclasses import FrozenInstanceError
import json

import pytest

from specroad.analyzers._reference_candidates import CANDIDATES
from specroad.analyzers._values import AnalyzerError
from specroad.analyzers.language_scores import decide_request, decide_scores
from test_analyzer_reference import controlled
from test_analyzer_text import language_request


@pytest.mark.parametrize('score,published,status', [
    (0.8999999999994, '0.899999999999', 'undetermined'),
    (0.8999999999996, '0.900000000000', 'detected'),
    (0.9, '0.900000000000', 'detected'),
    (0.9000000000005, '0.900000000000', 'detected'),
    (0.9000000000015, '0.900000000002', 'detected'),
])
def test_minimum_uses_the_published_half_even_score_inclusively(score, published, status):
    result = decide_scores([('fr', 1 - score), ('en', score)])
    assert result.status == status and result.scores[0] == ('en', published)
    assert result.language == ('en' if status == 'detected' else None)
    assert result.reason == (None if status == 'detected' else 'low_score_or_margin')


@pytest.mark.parametrize('score,margin,status', [
    (0.55, '0.100000000000', 'detected'),
    (0.55, '0.100000000001', 'undetermined'),
    (0.5499999999996, '0.100000000000', 'detected'),
    (0.5499999999994, '0.100000000000', 'undetermined'),
])
def test_margin_is_subtracted_exactly_after_quantization(score, margin, status):
    result = decide_scores([('en', score), ('fr', 1 - score)], min_score='0.5', min_margin=margin)
    assert result.status == status
    if status == 'detected':
        assert result.scores == (('en', '0.550000000000'), ('fr', '0.450000000000'))


def test_top_two_ties_are_broken_by_code_using_the_published_values():
    result = decide_scores([('fr', 0.5), ('en', 0.5), ('de', 0.0)])
    assert result.scores == (('en', '0.500000000000'), ('fr', '0.500000000000'))
    assert result.status == 'undetermined' and result.language is None
    inclusive = decide_scores([('fr', 0.5000000000001), ('en', 0.4999999999999)],
                              min_score='0.5', min_margin='0')
    assert inclusive.language == 'en' and inclusive.scores == result.scores


def test_only_normalized_uncalibrated_model_score_strings_are_serialized():
    result = decide_scores([('en', 0.9), ('fr', 0.1)])
    data = json.loads(json.dumps(result.data, allow_nan=False))
    assert data == dict(status='detected', reason=None, language='en',
        score_semantics='normalized_uncalibrated_model_scores', scores=[
            dict(language='en', score='0.900000000000'), dict(language='fr', score='0.100000000000')])
    data['scores'][0]['score'] = '0'
    assert result.scores[0][1] == '0.900000000000'
    with pytest.raises(FrozenInstanceError):
        result.language = 'de'


@pytest.mark.parametrize('field', ['min_score', 'min_margin'])
@pytest.mark.parametrize('value', [0.9, True, None, '', 'nan', 'Infinity', '-0.1', '1.1',
                                 '0.1234567890123', '1e-1', ' 0.9', '0.9 ', '０.９'])
def test_invalid_thresholds_fail_before_the_backend_even_for_short_text(monkeypatch, field, value):
    calls, owners = controlled(monkeypatch)
    with pytest.raises(AnalyzerError, match=field) as caught:
        decide_request(language_request(['x'], **{field: value}))
    assert caught.value.exit_code == 2 and calls == owners == []


@pytest.mark.parametrize('threshold', ['0', '0.000000000000', '1', '1.000000000000'])
def test_threshold_range_endpoints_are_valid(threshold):
    result = decide_scores([('en', 1.0), ('fr', 0.0)], min_score=threshold, min_margin=threshold)
    assert result.status == 'detected'


def test_request_decision_retains_every_subject_and_original_binding(monkeypatch):
    rows = [(code, 0.9 if code == 'en' else 0.1 if code == 'fr' else 0.0) for code in CANDIDATES]
    calls, owners = controlled(monkeypatch, rows=rows)
    request = language_request(['Original e\u0301 and mixed code (); ' * 3, 'short'])
    before = request.canonical_bytes
    result = decide_request(request)
    assert request.canonical_bytes == before
    assert (result.request_id, result.snapshot_sha256, result.descriptor_sha256) == (
        request.data['request_id'], request.data['snapshot_sha256'], request.data['analyzers'][0]['descriptor_sha256'])
    assert result.min_score == '0.900000000000' and result.min_margin == '0.100000000000'
    assert result.min_text_codepoints == 20 and result.preprocessing_version == 'ascii-edge-codepoints-v1'
    originals = sorted(request.data['subjects'], key=lambda s: s['subject_key'])
    assert [(s.subject_key, s.value_sha256) for s in result.subjects] == [
        (s['subject_key'], s['value_sha256']) for s in originals]
    for subject, original in zip(result.subjects, originals):
        assert subject.decision.status == ('undetermined' if original['value'] == 'short' else 'detected')
        assert subject.decision.reason == ('insufficient_text' if original['value'] == 'short' else None)
    assert len(calls) == len(owners) == 1 and owners[0]() is None
    assert result.engine.candidates == CANDIDATES


def test_score_threshold_changes_are_bound_to_distinct_requests(monkeypatch):
    rows = [(code, 0.8 if code == 'en' else 0.2 if code == 'fr' else 0.0) for code in CANDIDATES]
    controlled(monkeypatch, rows=rows)
    left = language_request(['original statement text ' * 3])
    right = language_request(['original statement text ' * 3], min_score='0.8')
    assert left.data['subjects'] == right.data['subjects']
    assert left.data['snapshot_sha256'] != right.data['snapshot_sha256']
    assert decide_request(left).subjects[0].decision.status == 'undetermined'
    assert decide_request(right).subjects[0].decision.status == 'detected'
