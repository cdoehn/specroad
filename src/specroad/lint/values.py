"""Owned, versioned glossary and literal-policy values; no execution or I/O."""
from dataclasses import dataclass
import re

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..storage.domain_artifact import DomainArtifact
from ..storage.json_reader import parse_json_object
from ._contract import _fail, _text, _language, _pointer, _term_id


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

    def __init__(self, raw: bytes):
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
                if group == "fields":
                    _pointer(item, at)
                if group == "term_ids":
                    _term_id(item, at)
                if item in seen:
                    _fail("literal_duplicate_selection", at)
                seen.add(item)
        seen_references = set()
        for i, reference in enumerate(value["references"]):
            at = "/references/" + str(i)
            if type(reference) is not dict or set(reference) != {"pointer", "by"}:
                _fail("literal_reference_fields", at)
            _pointer(reference["pointer"], at + "/pointer")
            if type(reference["by"]) is not str or reference["by"] not in ("id", "name"):
                _fail("literal_reference_mode", at + "/by")
            if reference["pointer"] in seen_references:
                _fail("literal_duplicate_reference_selection", at + "/pointer")
            seen_references.add(reference["pointer"])
        encoded = canonical_json_bytes(value)
        object.__setattr__(self, "source_bytes", raw)
        object.__setattr__(self, "_encoded", encoded)
        object.__setattr__(self, "sha256", canonical_json_sha256(value))

    @classmethod
    def from_value(cls, value: dict):
        return cls(canonical_json_bytes(value))

    @property
    def data(self):
        return parse_json_object(self._encoded)

