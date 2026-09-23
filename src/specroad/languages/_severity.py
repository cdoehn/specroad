"""Language finding policy delegates exit thresholds to the existing contract."""
from ..model.language_policy import LanguagePolicyError
from ..cli.option_values import ResolvedOptions, policy_exit_code, OptionResolutionError


def failure_options(fail_on, strict):
    if type(strict) is not bool:
        raise LanguagePolicyError("language_strict_boolean_required")
    try:
        # Explicit bad thresholds are errors even if strict would override them.
        policy_exit_code((), ResolvedOptions(None, None, {"fail_on": fail_on}, {}))
    except OptionResolutionError as error:
        raise LanguagePolicyError("language_invalid_fail_threshold") from error
    return ResolvedOptions(None, None, {"fail_on": "warning" if strict else fail_on}, {})


def language_findings(observed, policy, matched):
    findings = []
    def add(code, action, reason):
        if action != "allow":
            findings.append({"code": code, "severity": action, "reason": reason, "pointer": "/language"})
    if not observed.syntax_valid:
        add("SRV177", "error", "invalid_language_tag")
        return findings
    if not matched:
        add("SRV179", policy["disallowed_language"], "disallowed_language")
    if observed.registry_state == "unverified_registry":
        add("SRV178", policy["unverified_registry"], "unverified_registry")
    if observed.unspecified:
        add("SRV181", policy["unspecified_language"], "unspecified_language")
    return findings


def findings_exit_code(observed, findings, options):
    if not observed.syntax_valid:
        return 3
    return policy_exit_code([d["severity"] for d in findings], options)
