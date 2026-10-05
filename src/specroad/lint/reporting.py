"""Deterministic lint observations, explicitly NOT linguistic approval.

This is the single reporting boundary for future adapters. Inapplicable checks
remain distinct from passed checks; no full-inventory or language-quality claim
can be inferred from an empty diagnostic list.
"""
from ..model.canonical import canonical_json_sha256


def lint_findings_report(findings, *, fail_on, strict):
    """Project already observed findings under a caller-validated fail policy.

    This shared Core/reader projection does not decide check availability or
    source freshness. Those remain explicit responsibilities of each caller.
    """
    rank = {"info": 0, "warning": 1, "error": 2}
    threshold = "warning" if strict else fail_on
    diagnostics = sorted(findings, key=lambda d: (-rank[d["severity"]],
        d["path"] or "", d["artifact_id"], d["pointer"], d["code"],
        d.get("rule_id", ""), -1 if d.get("start") is None else d["start"]))
    return {"diagnostics": diagnostics, "failure_threshold": threshold,
            "findings_passed": not any(rank[d["severity"]] >= rank[threshold] for d in diagnostics)}


def _diagnostic_order(d):
    return (0 if d["severity"] == "error" else 1,
            d["path"] or "", d["artifact_id"], d["pointer"], d["code"],
            -1 if d["start"] is None else d["start"],
            -1 if d["end"] is None else d["end"],
            d["term_id"] or "", d["literal"] or "", d["reason"])


def literal_report(value, rules, glossary, policy, applicable, selected_terms, findings):
    """Return owned report data without modifying the caller's findings order."""
    diagnostics = sorted(findings, key=_diagnostic_order)
    return {"format_version": 1, "validation_scope": "selected_literal_fields_only",
        "artifact_id": value["id"], "artifact_sha256": canonical_json_sha256(value),
        "language": value["language"], "language_match": "exact_tag_ignore_case",
        "policy_sha256": policy.sha256, "glossary_sha256": glossary.sha256,
        "glossary_scope": "supplied_terms_only", "checked_fields": sorted(rules["fields"]),
        "matched_term_ids": selected_terms,
        "checks": {"forbidden_synonyms": "checked" if selected_terms else "not_applicable" if rules["term_ids"] else "not_configured",
                   "approved_placeholders": "checked" if value["maturity"] == "approved" else "not_applicable",
                   "term_references": ("checked" if applicable else "not_applicable") if rules["references"] else "not_configured"},
        "diagnostics": diagnostics, "literal_checks_passed": (not diagnostics if selected_terms or value["maturity"] == "approved" or (applicable and rules["references"]) else None),
        "linguistic_checks": {"modality": "not_available", "contradiction": "not_available",
                              "translation": "not_available", "single_obligation": "not_available"},
        "language_registry_checked": False, "language_detection_performed": False,
        "project_complete": False, "approval_granted": False}
