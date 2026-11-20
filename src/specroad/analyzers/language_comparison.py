"""Pure language-comparison-v1; no detector, permission policy or writes."""
from dataclasses import dataclass
import re

from ..model.language_registry import LanguageRegistry
from ..model.language_tags import parse_language_tag
from ._values import require
from .language_scores import ScoreDecision


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
