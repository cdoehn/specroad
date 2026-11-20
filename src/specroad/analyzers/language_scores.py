"""Exact decisions on published, normalized, uncalibrated model scores.

This is a decision value, not language-tag comparison, a final worker report,
calibrated confidence, Evidence or a release-quality claim.
"""
from dataclasses import dataclass

from ._reference_candidates import CANDIDATES
from ._values import AnalyzerError, require
from ._score_values import (normalized_total_is_valid, SCALE, QUANTUM as QUANTUM,
    format_units as format_units, score_units as score_units, parse_threshold as parse_threshold)
from .language_text import prepare_request, request_policy


SCORE_SEMANTICS = 'normalized_uncalibrated_model_scores'

__all__ = ('ScoreDecision', 'SubjectDecision', 'LanguageDecision', 'decide_scores',
           'decide_request', 'SCORE_SEMANTICS', 'SCALE', 'QUANTUM', 'format_units',
           'score_units', 'parse_threshold')


@dataclass(frozen=True)
class ScoreDecision:
    status: str
    reason: str | None
    language: str | None
    scores: tuple

    @property
    def data(self):
        return dict(status=self.status, reason=self.reason, language=self.language,
            score_semantics=SCORE_SEMANTICS,
            scores=[dict(language=code, score=score) for code, score in self.scores])


def decide_scores(rows, *, min_score='0.900000000000', min_margin='0.100000000000'):
    """Publish top two half-even values, then use only those values to decide."""
    minimum, margin = parse_threshold(min_score, 'min_score'), parse_threshold(min_margin, 'min_margin')
    try:
        require(type(rows) in (list, tuple) and len(rows) >= 2, 'invalid_backend_output', exit_code=5)
        ranked = []
        for row in rows:
            require(type(row) in (list, tuple) and len(row) == 2, 'invalid_backend_output', exit_code=5)
            code, score = row
            require(type(code) is str and code in (*CANDIDATES, 'und', 'zxx'),
                    'invalid_backend_output', exit_code=5)
            ranked.append((code, score_units(score)))
        require(len({code for code, _ in ranked}) == len(ranked), 'invalid_backend_output', exit_code=5)
        require(normalized_total_is_valid(ranked), 'invalid_backend_output', exit_code=5)
    except AnalyzerError:
        return ScoreDecision('failed', 'invalid_backend_output', None, ())
    ranked.sort(key=lambda row: (-row[1], row[0]))
    best, second = ranked[:2]
    published = tuple((code, format_units(score)) for code, score in (best, second))
    if best[0] in ('und', 'zxx'):
        reason = 'backend_abstention' if best[0] == 'und' else 'non_linguistic'
        return ScoreDecision('undetermined', reason, None, published)
    if best[1] < minimum or best[1] - second[1] < margin:
        return ScoreDecision('undetermined', 'low_score_or_margin', None, published)
    return ScoreDecision('detected', None, best[0], published)


@dataclass(frozen=True)
class SubjectDecision:
    subject_key: str
    value_sha256: str
    decision: ScoreDecision


@dataclass(frozen=True)
class LanguageDecision:
    request_id: str
    snapshot_sha256: str
    descriptor_sha256: str
    preprocessing_version: str
    min_text_codepoints: int
    min_score: str
    min_margin: str
    engine: object
    subjects: tuple


def decide_request(request):
    """Join length, availability and score decisions without losing bindings."""
    _, _, policy = request_policy(request)
    minimum = format_units(parse_threshold(policy['min_score'], 'min_score'))
    margin = format_units(parse_threshold(policy['min_margin'], 'min_margin'))
    prepared = prepare_request(request)
    subjects = []
    for subject in prepared.subjects:
        if subject.status == 'ranked':
            decision = decide_scores(subject.scores, min_score=minimum, min_margin=margin)
        else:
            decision = ScoreDecision(subject.status, subject.reason, None, ())
        subjects.append(SubjectDecision(subject.subject_key, subject.value_sha256, decision))
    return LanguageDecision(prepared.request_id, prepared.snapshot_sha256,
        prepared.descriptor_sha256, prepared.preprocessing_version, prepared.min_text_codepoints,
        minimum, margin, prepared.engine, tuple(subjects))
