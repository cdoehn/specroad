"""Ordered abstention, invalid whole rankings and context-independent values."""
from decimal import (DefaultContext, Inexact, InvalidOperation, Overflow, ROUND_DOWN,
                     ROUND_UP, Rounded, Underflow, localcontext)

import pytest

from specroad.analyzers._reference_candidates import CANDIDATES
from specroad.analyzers._values import AnalyzerError
from specroad.analyzers.language_scores import decide_request, decide_scores
from test_analyzer_reference import controlled
from test_analyzer_text import language_request


@pytest.mark.parametrize('label,reason', [('und', 'backend_abstention'), ('zxx', 'non_linguistic')])
@pytest.mark.parametrize('minimum,margin', [('0', '0'), ('1', '1')])
def test_backend_abstention_precedes_score_thresholds(label, reason, minimum, margin):
    result = decide_scores([(label, 0.6), ('en', 0.4)], min_score=minimum, min_margin=margin)
    assert (result.status, result.reason, result.language) == ('undetermined', reason, None)
    assert result.scores == ((label, '0.600000000000'), ('en', '0.400000000000'))


@pytest.mark.parametrize('label', ['und', 'zxx'])
def test_invalid_lower_rank_precedes_an_apparent_backend_abstention(label):
    result = decide_scores([(label, 0.9), ('en', float('nan'))])
    assert (result.status, result.reason, result.language, result.scores) == (
        'failed', 'invalid_backend_output', None, ())


@pytest.mark.parametrize('rows', [None, {}, [], [('en', 1.0)], ['en', 'fr'],
    [('en', 0.9), ('en', 0.1)], [('en', 0.9), ('fr',)],
    [('en', 0.9), ('FR', 0.1)], [('en', 0.9), ('en-US', 0.1)],
    [('en', 0.9), ('foreign', 0.1)], [('en', 0.9), (None, 0.1)],
    [('en', 0.9), (['fr'], 0.1)]])
def test_contradictory_ranking_shapes_and_labels_never_publish_a_decision(rows):
    result = decide_scores(rows)
    assert result.data == dict(status='failed', reason='invalid_backend_output', language=None,
        score_semantics='normalized_uncalibrated_model_scores', scores=[])


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -float('inf'), -0.0000000000001,
                               1.0000000000001, True, False, '0.1', None, {}])
def test_all_score_rows_are_validated_even_below_the_published_top_two(bad):
    result = decide_scores([('en', 0.9), ('fr', 0.1), ('de', bad)])
    assert (result.status, result.reason, result.scores) == ('failed', 'invalid_backend_output', ())


def test_entire_candidate_ranking_is_considered_not_only_a_prefix():
    rows = [(code, 1.0 if code == CANDIDATES[-1] else 0.0) for code in CANDIDATES]
    result = decide_scores(rows)
    assert result.language == CANDIDATES[-1]
    assert result.scores == ((CANDIDATES[-1], '1.000000000000'), (min(CANDIDATES[:-1]), '0.000000000000'))
    assert decide_scores(list(reversed(rows))) == result


@pytest.mark.parametrize('zero', [-0.0, 0, 0.0, 5e-324])
def test_zero_and_subnormal_scores_publish_a_canonical_unsigned_zero(zero):
    result = decide_scores([('fr', zero), ('en', 1.0)])
    assert result.scores == (('en', '1.000000000000'), ('fr', '0.000000000000'))


@pytest.mark.parametrize('rounding', [ROUND_DOWN, ROUND_UP])
def test_global_context_precision_rounding_traps_and_flags_cannot_change_decision(rounding):
    rows = [('en', 0.9000000000015), ('fr', 0.0999999999985)]
    expected = dict(status='detected', reason=None, language='en',
        score_semantics='normalized_uncalibrated_model_scores', scores=[
            dict(language='en', score='0.900000000002'), dict(language='fr', score='0.099999999998')])
    with localcontext() as context:
        context.prec, context.rounding, context.Emin, context.Emax = 1, rounding, -1, 1
        for signal in (Inexact, Rounded, InvalidOperation, Overflow, Underflow):
            context.traps[signal] = True
            context.flags[signal] = True
        before = (context.copy(), dict(context.flags), dict(context.traps))
        assert decide_scores(rows).data == expected
        assert (context.prec, context.rounding, context.Emin, context.Emax) == (1, rounding, -1, 1)
        assert dict(context.flags) == before[1] and dict(context.traps) == before[2]


def test_default_context_changes_cannot_change_a_later_explicit_score_context(monkeypatch):
    monkeypatch.setattr(DefaultContext, 'prec', 1)
    monkeypatch.setattr(DefaultContext, 'rounding', ROUND_DOWN)
    monkeypatch.setattr(DefaultContext, 'Emin', -1)
    monkeypatch.setattr(DefaultContext, 'Emax', 1)
    result = decide_scores([('en', 0.9000000000015), ('fr', 0.0999999999985)])
    assert result.scores == (('en', '0.900000000002'), ('fr', '0.099999999998'))


def test_backend_failure_and_short_text_are_not_turned_into_low_scores(monkeypatch):
    attempts = []
    def fail():
        attempts.append(True)
        raise AnalyzerError('analyzer_model_unavailable', exit_code=5)
    monkeypatch.setattr('specroad.analyzers._model_session.load_reference_model', fail)
    request = language_request(['full original text ' * 4, 'short', 'another full text ' * 4],
                               min_score='0', min_margin='0')
    result = decide_request(request)
    assert attempts == [True]
    assert sorted(s.decision.status for s in result.subjects) == ['unavailable', 'unavailable', 'undetermined']
    assert all(s.decision.language is None and not s.decision.scores for s in result.subjects)
    assert result.engine is None


def test_malformed_real_backend_shape_stays_failed_at_the_request_boundary(monkeypatch):
    controlled(monkeypatch, rows=[('en', 1.0)])
    result = decide_request(language_request(['full original text ' * 4], min_score='0', min_margin='0'))
    assert result.subjects[0].decision.status == 'failed'
    assert result.subjects[0].decision.reason == 'invalid_backend_output'
    assert result.subjects[0].decision.language is None and not result.subjects[0].decision.scores


@pytest.mark.parametrize('field', ['min_score', 'min_margin'])
def test_invalid_thresholds_are_input_errors_even_with_invalid_backend_rows(field):
    with pytest.raises(AnalyzerError, match=field) as caught:
        decide_scores(None, **{field: 'NaN'})
    assert caught.value.exit_code == 2


@pytest.mark.parametrize('rows', [[('en', 0.0), ('fr', 0.0)],
    [('en', 0.9), ('fr', 0.8)], [('en', 0.3), ('fr', 0.2)]])
def test_impossible_normalized_total_fails_even_with_zero_thresholds(rows):
    result = decide_scores(rows, min_score='0', min_margin='0')
    assert (result.status, result.reason, result.language, result.scores) == (
        'failed', 'invalid_backend_output', None, ())


def test_total_validation_allows_the_error_implied_by_half_even_rounding():
    result = decide_scores([('en', 0.3333333333335), ('fr', 0.3333333333335),
                            ('de', 0.333333333333)], min_score='0.3', min_margin='0')
    assert result.status == 'detected' and result.language == 'en'
    assert result.scores == (('en', '0.333333333334'), ('fr', '0.333333333334'))


@pytest.mark.parametrize('value,expected', [
    (0.3333333432674408, '0.333333343267'),
    (0.3333333134651184, '0.333333313465'),
])
def test_binary32_normalization_residual_is_not_a_backend_failure(value, expected):
    # Exact binary32 neighbours around 1/3; do not renormalize the originals.
    rows = [('fr', value), ('en', value), ('de', value)]
    result = decide_scores(rows, min_score='0.3', min_margin='0')
    assert (result.status, result.reason, result.language) == ('detected', None, 'de')
    assert result.scores == (('de', expected), ('en', expected))
    assert decide_scores(rows).reason == 'low_score_or_margin'


def test_complete_binary32_uniform_ranking_keeps_its_original_quantized_values():
    # Nearest binary32 to 1/140. The complete score sum is not exactly one.
    rows = [(code, 0.0071428571827709675) for code in CANDIDATES]
    result = decide_scores(rows, min_score='0', min_margin='0')
    first, second = sorted(CANDIDATES)[:2]
    assert (result.status, result.language) == ('detected', first)
    assert result.scores == ((first, '0.007142857183'), (second, '0.007142857183'))


@pytest.mark.parametrize('top', [0.89998, 0.90002])
def test_total_error_larger_than_binary32_roundoff_still_fails(top):
    rows = [(code, top if code == 'en' else 0.1 if code == 'fr' else 0.0)
            for code in CANDIDATES]
    result = decide_scores(rows, min_score='0', min_margin='0')
    assert (result.status, result.reason, result.language, result.scores) == (
        'failed', 'invalid_backend_output', None, ())
