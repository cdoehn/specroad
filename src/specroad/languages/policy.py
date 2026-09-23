"""Declaration policy, independent of source lookup and human interpretation."""
from ..model.language_policy import LanguagePolicy, LanguagePolicyError, COMPARISONS
from ..model.language_registry import LanguageRegistry
from ..model.language_packages import range_matches
from ..cli.option_values import ResolvedOptions, policy_exit_code, OptionResolutionError


def _assessment(registry, language):
    if type(registry) is not LanguageRegistry:
        raise LanguagePolicyError("language_registry_required")
    # Reparse to verify the captured bytes, not caller-replaced cache fields.
    checked = LanguageRegistry(registry.source_bytes, expected_sha256=registry.sha256,
                               expected_version=registry.version)
    return checked.inspect(language)


def language_comparison_key(language, *, registry, comparison):
    """S.5 comparison only, NOT a container-mixing or detector judgement."""
    if type(comparison) is not str or comparison not in COMPARISONS:
        raise LanguagePolicyError("language_policy_comparison")
    tag = _assessment(registry, language)
    if not tag.syntax_valid:
        raise LanguagePolicyError("invalid_language_tag", pointer="/language")
    if tag.unspecified:
        return None
    canonical = tag.canonical.lower()
    if comparison == "exact_tag" or tag.registry_state in ("private_use", "unverified_registry"):
        return canonical
    return canonical.split("-", 1)[0]


def evaluate_language(language, *, policy, registry, fail_on="error", strict=False):
    """Return a complete *declaration-only* observation, never a storage permit.

Missing/nontext and invalid syntax are hard schema errors (3), not downgradable
policy findings. Warnings retain their severity even when strict makes exit=1.
"""
    if type(policy) is not LanguagePolicy:
        raise LanguagePolicyError("language_policy_required")
    if type(strict) is not bool:
        raise LanguagePolicyError("language_strict_boolean_required")
    options = ResolvedOptions(None, None, {"fail_on": "warning" if strict else fail_on}, {})
    try:
        # Even under strict, an explicitly invalid threshold must not disappear.
        policy_exit_code((), ResolvedOptions(None, None, {"fail_on": fail_on}, {}))
    except OptionResolutionError as error:
        raise LanguagePolicyError("language_invalid_fail_threshold") from error
    observed = _assessment(registry, language)
    data = policy.data
    findings = []
    def finding(code, action, reason):
        if action != "allow":
            findings.append({"code": code, "severity": action, "reason": reason, "pointer": "/language"})
    matched = []
    if not observed.syntax_valid:
        finding("SRV177", "error", "invalid_language_tag")
    else:
        matched = [item for item in data["allowed_ranges"] if range_matches(item, language)]
        if not matched:
            finding("SRV179", data["disallowed_language"], "disallowed_language")
        if observed.registry_state == "unverified_registry":
            finding("SRV178", data["unverified_registry"], "unverified_registry")
        if observed.unspecified:
            finding("SRV181", data["unspecified_language"], "unspecified_language")
    exit_code = 3 if not observed.syntax_valid else policy_exit_code([d["severity"] for d in findings], options)
    return {"format_version": 1, "validation_scope": "declared_language_only",
        "assessment": observed.as_dict(), "policy": data, "policy_sha256": policy.sha256,
        "matched_ranges": matched, "range_allowed": bool(matched),
        "metadata_policy_passed": not any(d["severity"] == "error" for d in findings),
        "diagnostics": findings, "fail_on": options.values["fail_on"], "strict": strict,
        "exit_code": exit_code, "comparison_key": (language_comparison_key(language,
            registry=registry, comparison=data["mixed_languages"]["comparison"]) if observed.syntax_valid else None),
        "content_support": "utf8", "language_detection_performed": False,
        "linguistic_validation": False, "project_complete": False, "approval_granted": False}
