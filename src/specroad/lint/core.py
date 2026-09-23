"""Orchestrate explicit, read-only literal checks over owned input values."""
from ..model.artifact_schemas import validate_common_fields
from ..model.canonical import canonical_json_bytes
from ..storage.json_reader import parse_json_object
from ._contract import LiteralLintError, _fail, _language
from ._matching import _selected_texts, _occurrences, _reference_findings
from .values import Glossary, LiteralPolicy
from .reporting import literal_report


def lint_literals(artifact: dict, *, glossary: Glossary, policy: LiteralPolicy,
                  path: str | None = None) -> dict:
    """Observe selected fields, never infer whole-project or linguistic quality.

Common structural validation precedes lint. Approved-only placeholder checks do
not authorize approval. No write, registry lookup, package fallback or I/O occurs.
The caller owns stability during capture of its mutable JSON argument.
"""
    if type(glossary) is not Glossary or type(policy) is not LiteralPolicy:
        _fail("literal_checked_inputs_required")
    if path is not None and type(path) is not str:
        _fail("literal_diagnostic_path_required")
    value = parse_json_object(canonical_json_bytes(artifact))
    validate_common_fields(value)
    if "language" not in value:
        _fail("literal_declared_language_required", "/language")
    declared = _language(value["language"])
    rules = policy.data
    applicable = declared == _language(rules["language"])
    terms = {t["id"]: t for t in glossary.terms}
    for i, term_id in enumerate(rules["term_ids"]):
        if term_id not in terms:
            _fail("literal_selected_term_missing", "/term_ids/" + str(i))
    texts = _selected_texts(value, rules["fields"])
    patterns = []
    selected_terms = []
    if applicable:
        for term_id in sorted(rules["term_ids"]):
            term = terms[term_id]
            if _language(term["language"]) != declared:
                continue
            selected_terms.append(term_id)
            for literal in sorted(set(term["forbidden_synonyms"])):
                patterns.append((literal, "SRV053", "warning", "forbidden_synonym", term_id))
    # This exact Core list follows SR-REQ-0097. A profile list cannot suppress it.
    placeholders = {"TBD", "TODO", "FIXME"}
    if applicable:
        placeholders.update(rules["placeholders"])
    if value["maturity"] == "approved":
        for literal in sorted(placeholders):
            patterns.append((literal, "SRV033", "error", "open_placeholder", None))
    diagnostics = []
    for field, text in texts:
        for literal, code, severity, reason, term_id in patterns:
            for start, end in _occurrences(text, literal):
                diagnostics.append({"code": code, "severity": severity, "reason": reason,
                    "artifact_id": value["id"], "path": path, "pointer": field,
                    "start": start, "end": end, "offset_unit": "unicode_codepoint",
                    "literal": literal, "term_id": term_id, "candidate_ids": []})
    if applicable:
        diagnostics.extend(_reference_findings(value, terms, rules["references"], declared, path))
    return literal_report(value, rules, glossary, policy, applicable,
                          selected_terms, diagnostics)
