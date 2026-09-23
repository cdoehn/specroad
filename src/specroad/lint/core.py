"""Literal checks over explicitly selected text fields and supplied term records.

No tokenizer, morphology, translation, modal-word inference or analyzer. Pattern
matching uses exact Unicode scalar substrings (including overlaps), with no
case folding, normalization, whitespace rewriting or inferred word boundaries.
Language matching here is case-insensitive exact-tag equality, NOT the future
Basic Filtering/package composition layer. A report is not project approval.
"""
from dataclasses import dataclass
import re

from ..model.artifact_schemas import validate_common_fields
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.domain_fields import reference_schema
from ..model._schema import validate_builtin
from ..model.errors import ModelError
from ..model.language_tags import parse_language_tag
from ..storage.domain_artifact import DomainArtifact
from ..storage.json_reader import parse_json_object
from ..srx.errors import SrxError
from ..srx.pointers import parse_pointer, resolve_tokens
from ..srx.types import MISSING


class LiteralLintError(ModelError):
    """Invalid supplied data or selection, not a passed or empty lint result."""
    exit_code = 3


def _fail(reason, pointer=""):
    raise LiteralLintError(reason, pointer=pointer)


def _text(value, pointer):
    if type(value) is not str or not value.strip():
        _fail("literal_nonempty_text_required", pointer)


def _language(value):
    return parse_language_tag(value).canonical.lower()


def _pointer(value, at):
    try:
        tokens = parse_pointer(value, rule_id="literal-policy", at=at)
    except SrxError as error:
        raise LiteralLintError("literal_invalid_pointer", pointer=at) from error
    if not tokens:
        _fail("literal_field_pointer_required", at)
    return tokens


def _term_id(value, pointer):
    try:
        validate_builtin(value, reference_schema("TERM"))
    except ModelError as error:
        raise LiteralLintError("literal_invalid_term_id", pointer=pointer) from error


@dataclass(frozen=True, init=False)
class Glossary:
    """Owned validated terms; completeness covers only these supplied records."""
    _terms: tuple
    sha256: str

    def __init__(self, terms):
        if type(terms) not in (tuple, list):
            _fail("glossary_sequence_required")
        captured = []
        seen = set()
        for term in terms:
            if type(term) is not DomainArtifact or term.artifact_type != "term":
                _fail("glossary_term_record_required")
            # Capture/revalidate source bytes, never mutable caller projections.
            item = DomainArtifact(term.source_bytes, expected_type="term", path=term.path)
            if item.id in seen:
                _fail("glossary_duplicate_id")
            seen.add(item.id)
            captured.append(item)
        captured.sort(key=lambda t: t.id)
        object.__setattr__(self, "_terms", tuple(captured))
        object.__setattr__(self, "sha256", canonical_json_sha256([t.data for t in captured]))

    @property
    def terms(self):
        return tuple(item.data for item in self._terms)


@dataclass(frozen=True, init=False)
class LiteralPolicy:
    """Versioned library input, not a new persisted profile or language package.

The caller explicitly supplies fields, selected term IDs and additional literal
placeholders. Nothing is extracted from prose, imported, or auto-configured.
"""
    source_bytes: bytes
    _encoded: bytes
    sha256: str

    def __init__(self, raw):
        if type(raw) is not bytes:
            _fail("literal_policy_bytes_required")
        value = parse_json_object(raw)
        required = {"format_version", "policy_id", "version", "language", "fields",
                    "term_ids", "placeholders", "references"}
        if set(value) != required:
            _fail("literal_policy_fields")
        if type(value["format_version"]) is not int or value["format_version"] != 1:
            _fail("literal_policy_version", "/format_version")
        _text(value["policy_id"], "/policy_id")
        if type(value["version"]) is not str or re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", value["version"]) is None:
            _fail("literal_policy_exact_version", "/version")
        _language(value["language"])
        for group in ("fields", "term_ids", "placeholders", "references"):
            if type(value[group]) is not list:
                _fail("literal_policy_array_required", "/" + group)
        if not value["fields"]:
            _fail("literal_fields_required", "/fields")
        for group in ("fields", "term_ids", "placeholders"):
            seen = set()
            for i, item in enumerate(value[group]):
                at = "/" + group + "/" + str(i)
                _text(item, at)
                if group == "fields": _pointer(item, at)
                if group == "term_ids": _term_id(item, at)
                if item in seen: _fail("literal_duplicate_selection", at)
                seen.add(item)
        # The first working slice explicitly rejects unimplemented references.
        if value["references"]:
            _fail("literal_reference_checks_not_available", "/references")
        encoded = canonical_json_bytes(value)
        object.__setattr__(self, "source_bytes", raw)
        object.__setattr__(self, "_encoded", encoded)
        object.__setattr__(self, "sha256", canonical_json_sha256(value))

    @classmethod
    def from_value(cls, value):
        return cls(canonical_json_bytes(value))

    @property
    def data(self):
        return parse_json_object(self._encoded)


def _selected_texts(value, fields):
    result = []
    for field in fields:
        try:
            text = resolve_tokens(value, _pointer(field, field), rule_id="literal-policy", at=field)
        except SrxError as error:
            raise LiteralLintError("literal_field_access_error", pointer=field) from error
        if text is MISSING:
            _fail("literal_selected_field_missing", field)
        if type(text) is not str:
            _fail("literal_selected_field_not_text", field)
        result.append((field, text))
    return result


def _occurrences(text, literal):
    start = 0
    while True:
        found = text.find(literal, start)
        if found < 0:
            return
        yield found, found + len(literal)
        start = found + 1


def lint_literals(artifact, *, glossary, policy, path=None):
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
    diagnostics.sort(key=lambda d: (0 if d["severity"] == "error" else 1,
        d["path"] or "", d["artifact_id"], d["pointer"], d["code"],
        d["start"], d["end"], d["term_id"] or "", d["literal"]))
    return {"format_version": 1, "validation_scope": "selected_literal_fields_only",
        "artifact_id": value["id"], "artifact_sha256": canonical_json_sha256(value),
        "language": value["language"], "language_match": "exact_tag_ignore_case",
        "policy_sha256": policy.sha256, "glossary_sha256": glossary.sha256,
        "glossary_scope": "supplied_terms_only", "checked_fields": sorted(rules["fields"]),
        "matched_term_ids": selected_terms,
        "checks": {"forbidden_synonyms": "checked" if selected_terms else "not_applicable" if rules["term_ids"] else "not_configured",
                   "approved_placeholders": "checked" if value["maturity"] == "approved" else "not_applicable",
                   "term_references": "not_configured"},
        "diagnostics": diagnostics, "literal_checks_passed": (not diagnostics if selected_terms or value["maturity"] == "approved" else None),
        "linguistic_checks": {"modality": "not_available", "contradiction": "not_available",
                              "translation": "not_available", "single_obligation": "not_available"},
        "project_complete": False, "approval_granted": False}
