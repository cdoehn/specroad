"""Exact Unicode substring and explicit reference checks, without NLP claims."""
from ..srx.errors import SrxError
from ..srx.pointers import resolve_tokens
from ..srx.types import MISSING
from ._contract import LiteralLintError, _fail, _language, _pointer, _term_id


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



def _reference_findings(value, terms, references, declared, path):
    names = {}
    for term_id, term in terms.items():
        if _language(term["language"]) == declared:
            for name in set([term["term"], *term["synonyms"]]):
                names.setdefault(name, set()).add(term_id)
    result = []
    for reference in references:
        pointer = reference["pointer"]
        try:
            text = resolve_tokens(value, _pointer(pointer, pointer), rule_id="literal-reference", at=pointer)
        except SrxError as error:
            raise LiteralLintError("literal_reference_access_error", pointer=pointer) from error
        candidates = []
        if text is MISSING:
            reason = "undefined_term_reference"
        elif type(text) is not str or not text.strip():
            reason = "invalid_term_reference"
        elif reference["by"] == "id":
            try:
                _term_id(text, pointer)
            except LiteralLintError:
                reason = "invalid_term_reference"
            else:
                if text not in terms:
                    reason = "undefined_term_reference"
                elif _language(terms[text]["language"]) != declared:
                    reason = "term_reference_language_mismatch"
                    candidates = [text]
                else:
                    continue
        else:
            candidates = sorted(names.get(text, ()))
            if len(candidates) == 1:
                continue
            reason = "ambiguous_term_reference" if candidates else "undefined_term_reference"
        result.append({"code": "SRV053", "severity": "warning", "reason": reason,
            "artifact_id": value["id"], "path": path, "pointer": pointer,
            "start": 0 if type(text) is str else None,
            "end": len(text) if type(text) is str else None,
            "offset_unit": "unicode_codepoint", "literal": text if type(text) is str else None,
            "term_id": None, "candidate_ids": candidates})
    return result

