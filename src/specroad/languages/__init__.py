"""Explicit language policy and package composition; no detection or writes."""
from .policy import evaluate_language, language_comparison_key
from .packages import compose_language_packages, LanguageComposition

__all__ = ("evaluate_language", "language_comparison_key", "compose_language_packages", "LanguageComposition")
