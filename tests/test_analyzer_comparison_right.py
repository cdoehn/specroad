"""Preserved declarations and exhaustive, bound comparisons without detection."""
from dataclasses import replace

import pytest

from specroad.analyzers._values import AnalyzerError
from specroad.analyzers.language_comparison import compare_language, compare_decisions
from specroad.analyzers.language_scores import LanguageDecision, ScoreDecision, SubjectDecision
from specroad.analyzers.requests import create_request
from specroad.storage.language_registry import bundled_language_registry
from support.languages import load_registry
from test_analyzer_comparison import detected
from test_analyzer_text import language_request


@pytest.mark.parametrize('declared', ['en-Qaaa', 'en-AA', 'en-ZZ', 'en-QQ', 'en-Fake',
    'en-zzzzz', 'en-u-ca-gregory', 'en-cmn', 'zzzz-Latn', 'i-klingon'])
def test_private_unknown_or_unresolved_precision_never_becomes_a_language_match(declared):
    result = compare_language(declared, detected('en'), registry=bundled_language_registry())
    assert result.status == 'unverifiable' and result.language_resolution is None
    assert result.declared_language == declared
    assert result.data['region_checked'] is result.data['script_checked'] is False


@pytest.mark.parametrize('code', ['zzzz', 'qaa', 'und', 'mul', 'zxx'])
def test_uncomparable_detected_codes_are_unverifiable_even_when_equal_to_declaration(code):
    result = compare_language(code, detected(code), registry=bundled_language_registry())
    assert result.status == 'unverifiable'


def test_knowledge_comes_from_the_explicit_registry_not_a_hidden_default():
    sparse, full = load_registry(), bundled_language_registry()
    assert compare_language('de', detected('de'), registry=sparse).status == 'unverifiable'
    assert compare_language('de', detected('de'), registry=full).status == 'compatible'
    assert sparse.sha256 != full.sha256


@pytest.mark.parametrize('decision', [None, {},
    ScoreDecision('ranked', None, 'en', ()), ScoreDecision('detected', 'low_score_or_margin', 'en', ()),
    ScoreDecision('detected', None, None, ()), ScoreDecision('detected', None, 'en-US', ()),
    ScoreDecision('detected', None, 'EN', ()), ScoreDecision('undetermined', 'insufficient_text', 'en', ())])
def test_invalid_decision_values_cannot_assert_compatibility(decision):
    with pytest.raises(AnalyzerError, match='analyzer_score_decision') as error:
        compare_language('en', decision, registry=bundled_language_registry())
    assert error.value.exit_code == 5


def request_and_decisions():
    raw = language_request(['long original text ' * 3] * 5).data
    declarations = ['en-US', 'en-IN', 'cmn-Hans-CN', 'zh-Hant-TW', 'x-company']
    for subject, declared in zip(raw['subjects'], declarations):
        subject['declared_language'] = declared
    raw['subjects'][1].pop('normative_force')
    raw.pop('contract_version'); raw.pop('snapshot_sha256')
    request = create_request(**{k: v for k, v in raw.items() if k != 'request_id'}, analysis_id=raw['request_id'])
    codes = ('en', 'fr', 'zh', 'zh', None)
    rows = tuple(SubjectDecision(s['subject_key'], s['value_sha256'], detected(code) if code else
        ScoreDecision('undetermined', 'insufficient_text', None, ())) for s, code in zip(raw['subjects'], codes))
    decisions = LanguageDecision(request.data['request_id'], request.data['snapshot_sha256'],
        request.data['analyzers'][0]['descriptor_sha256'], 'ascii-edge-codepoints-v1', 20,
        '0.900000000000', '0.100000000000', None, tuple(reversed(rows)))
    return request, decisions


def test_complete_comparison_preserves_original_declarations_force_hashes_and_nondecisions(monkeypatch):
    request, decisions = request_and_decisions()
    original = request.canonical_bytes
    registry = bundled_language_registry()
    def forbidden():
        raise AssertionError('comparison must not initialize a backend')
    monkeypatch.setattr('specroad.analyzers._model_session.load_reference_model', forbidden)
    result = compare_decisions(request, decisions, registry=registry)
    assert result.decision is decisions and result.registry_sha256 == registry.sha256
    assert request.canonical_bytes == original
    by_tag = {s.declared_language: s for s in result.subjects}
    expected = {'en-US': 'compatible', 'en-IN': 'mismatch', 'cmn-Hans-CN': 'compatible_coarse',
                'zh-Hant-TW': 'compatible', 'x-company': None}
    assert {k: v.comparison.status if v.comparison else None for k, v in by_tag.items()} == expected
    assert by_tag['cmn-Hans-CN'].comparison.language_resolution == 'macrolanguage_only'
    assert by_tag['zh-Hant-TW'].comparison.detected_language == 'zh'
    originals = sorted(request.data['subjects'], key=lambda s: s['subject_key'])
    assert [(s.subject_key, s.value_sha256, s.declared_language, s.normative_force) for s in result.subjects] == [
        (s['subject_key'], s['value_sha256'], s['declared_language'], s.get('normative_force')) for s in originals]
    assert by_tag['x-company'].decision.reason == 'insufficient_text'
    assert all(not s.comparison.data['region_checked'] and not s.comparison.data['script_checked']
               for s in result.subjects if s.comparison)


@pytest.mark.parametrize('field,value', [('request_id', 'reference:another'),
    ('snapshot_sha256', 'a' * 64), ('descriptor_sha256', 'b' * 64),
    ('preprocessing_version', 'foreign'), ('min_text_codepoints', 19),
    ('min_score', '0.800000000000'), ('min_margin', '0.200000000000')])
def test_decision_from_another_request_or_policy_is_rejected(field, value):
    request, decisions = request_and_decisions()
    with pytest.raises(AnalyzerError) as error:
        compare_decisions(request, replace(decisions, **{field: value}), registry=bundled_language_registry())
    assert error.value.exit_code == 6


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'foreign', 'value'])
def test_all_subject_bindings_are_required_before_returning_the_comparison(change):
    request, decisions = request_and_decisions()
    rows = decisions.subjects
    if change == 'missing':
        rows = rows[1:]
    elif change == 'duplicate':
        rows = rows + rows[:1]
    elif change == 'foreign':
        rows = (replace(rows[0], subject_key='a' * 64),) + rows[1:]
    else:
        rows = (replace(rows[0], value_sha256='b' * 64),) + rows[1:]
    with pytest.raises(AnalyzerError) as error:
        compare_decisions(request, replace(decisions, subjects=rows), registry=bundled_language_registry())
    assert error.value.exit_code == 6
