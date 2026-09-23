"""Compose registry observation, Basic Filtering, and stable severity decisions."""
from ..model.language_policy import LanguagePolicy, LanguagePolicyError, COMPARISONS
from ._registry import assess_declaration
from ._filtering import matching_ranges, comparison_key
from ._severity import failure_options, language_findings, findings_exit_code


def language_comparison_key(language, *, registry, comparison):
    """S.5 comparison only, NOT a container-mixing or detector judgement."""
    if type(comparison) is not str or comparison not in COMPARISONS:
        raise LanguagePolicyError("language_policy_comparison")
    observed = assess_declaration(registry, language)
    if not observed.syntax_valid:
        raise LanguagePolicyError("invalid_language_tag", pointer="/language")
    return comparison_key(observed, comparison)


def evaluate_language(language, *, policy, registry, fail_on="error", strict=False):
    """Observe one declaration; never a storage, linguistic or approval permit.

The same immutable registry observation is used for matching and comparison.
The failure threshold changes only the exit decision, never diagnostic severity.
"""
    if type(policy) is not LanguagePolicy:
        raise LanguagePolicyError("language_policy_required")
    options = failure_options(fail_on, strict)
    observed = assess_declaration(registry, language)
    data = policy.data
    matched = matching_ranges(data["allowed_ranges"], language) if observed.syntax_valid else []
    findings = language_findings(observed, data, matched)
    return {"format_version": 1, "validation_scope": "declared_language_only",
        "assessment": observed.as_dict(), "policy": data, "policy_sha256": policy.sha256,
        "matched_ranges": matched, "range_allowed": bool(matched),
        "metadata_policy_passed": not any(d["severity"] == "error" for d in findings),
        "diagnostics": findings, "fail_on": options.values["fail_on"], "strict": strict,
        "exit_code": findings_exit_code(observed, findings, options),
        "comparison_key": (comparison_key(observed, data["mixed_languages"]["comparison"])
                           if observed.syntax_valid else None),
        "content_support": "utf8", "language_detection_performed": False,
        "linguistic_validation": False, "project_complete": False, "approval_granted": False}
