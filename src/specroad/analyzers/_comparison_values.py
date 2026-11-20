"""Immutable comparison values; separate from matching and permissions."""
from dataclasses import dataclass

from .language_scores import LanguageDecision, ScoreDecision

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
