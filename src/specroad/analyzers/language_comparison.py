"""Pure language-comparison-v1; no detector, permission policy or writes."""
from dataclasses import dataclass
import re

from ..model.language_registry import LanguageRegistry
from ..model.language_tags import parse_language_tag
from ._values import require
from .language_scores import LanguageDecision, ScoreDecision, SubjectDecision
from ._score_values import format_units, parse_threshold
from ._text_policy import TEXT_POLICY_VERSION, request_policy


COMPARISON_VERSION = 'language-comparison-v1'


@dataclass(frozen=True)
class LanguageComparison:
    declared_language: str
    detected_language: str
    status: str
    language_resolution: str | None
    registry_version: str
    registry_sha256: str

    @property
    def data(self):
        return dict(comparison_version=COMPARISON_VERSION,
            declared_language=self.declared_language, detected_language=self.detected_language,
            status=self.status, language_resolution=self.language_resolution,
            region_checked=False, script_checked=False,
            registry_version=self.registry_version, registry_sha256=self.registry_sha256)


def compare_language(declared, decision, *, registry):
    """Compare a decided primary code; return None for a nondecision.

    The explicit native registry supplies knowledge, never language permission.
    Unknown/private declarations cannot be proved by a matching detector label.
    No preferred-value alias, region, script or specific language is inferred.
    """
    require(type(registry) is LanguageRegistry, 'analyzer_language_registry_required', exit_code=3)
    assessment = registry.inspect(declared)
    require(assessment.syntax_valid, 'analyzer_declared_language', exit_code=3)
    require(type(decision) is ScoreDecision and decision.status in (
        'detected', 'undetermined', 'unavailable', 'failed'), 'analyzer_score_decision', exit_code=5)
    if decision.status != 'detected':
        require(decision.language is None, 'analyzer_score_decision', exit_code=5)
        return None
    detected = decision.language
    require(decision.reason is None and type(detected) is str
            and re.fullmatch(r'[a-z]{2,8}', detected) is not None,
            'analyzer_score_decision', exit_code=5)
    tag = parse_language_tag(declared)
    known = registry.inspect(detected)
    status, resolution = 'unverifiable', None
    if (assessment.registry_state == known.registry_state == 'registered'
            and not assessment.unspecified and not known.unspecified and tag.language is not None):
        resolution = 'primary_language'
        if tag.language == detected:
            status = 'compatible'
        elif tag.language == 'cmn' and detected == 'zh':
            status, resolution = 'compatible_coarse', 'macrolanguage_only'
        else:
            status = 'mismatch'
    return LanguageComparison(declared, detected, status, resolution,
                              registry.version, registry.sha256)


@dataclass(frozen=True)
class ComparedSubject:
    subject_key: str
    value_sha256: str
    declared_language: str
    normative_force: str | None
    decision: ScoreDecision
    comparison: LanguageComparison | None


@dataclass(frozen=True)
class ComparedLanguage:
    decision: LanguageDecision
    registry_version: str
    registry_sha256: str
    subjects: tuple


def compare_decisions(request, decisions, *, registry):
    """Join only the exact owned request and decisions; never rerun a detector.

    The explicit registry binding accompanies this internal value. It is not a
    final worker report, EngineFingerprint, permission decision or Evidence.
    """
    data, descriptor, policy = request_policy(request)
    require(type(decisions) is LanguageDecision, 'analyzer_language_decision', exit_code=5)
    require(type(registry) is LanguageRegistry, 'analyzer_language_registry_required', exit_code=3)
    request.require_binding(request_id=decisions.request_id, snapshot_sha256=decisions.snapshot_sha256)
    require(decisions.descriptor_sha256 == descriptor['descriptor_sha256']
            and decisions.preprocessing_version == TEXT_POLICY_VERSION
            and decisions.min_text_codepoints == policy['min_text_codepoints']
            and decisions.min_score == format_units(parse_threshold(policy['min_score'], 'min_score'))
            and decisions.min_margin == format_units(parse_threshold(policy['min_margin'], 'min_margin')),
            'analyzer_decision_policy_mismatch', exit_code=6)
    require(type(decisions.subjects) is tuple and all(type(s) is SubjectDecision
            and type(s.subject_key) is str and type(s.value_sha256) is str for s in decisions.subjects),
            'analyzer_decision_subjects', exit_code=5)
    by_key = {s.subject_key: s for s in decisions.subjects}
    require(len(by_key) == len(decisions.subjects)
            and set(by_key) == {s['subject_key'] for s in data['subjects']},
            'analyzer_decision_subjects', exit_code=6)
    subjects = []
    for subject in sorted(data['subjects'], key=lambda s: s['subject_key']):
        selected = by_key[subject['subject_key']]
        require(selected.value_sha256 == subject['value_sha256'], 'analyzer_decision_value_mismatch', exit_code=6)
        comparison = compare_language(subject['declared_language'], selected.decision, registry=registry)
        subjects.append(ComparedSubject(subject['subject_key'], subject['value_sha256'],
            subject['declared_language'], subject.get('normative_force'), selected.decision, comparison))
    return ComparedLanguage(decisions, registry.version, registry.sha256, tuple(subjects))
