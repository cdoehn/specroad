"""Passive metadata field contracts. Names never identify executable adapters.

A namespace consists of two or more nonempty dot-separated components without
whitespace or control characters. There is no registration or ASCII-only rule.
Provenance uses the same locator/captured_at/excerpt/content_sha256 spelling as
Source records; source_id is an optional source-artifact reference. Checking
these shapes does not resolve a source or authenticate a hash.
"""

from ._schema import validate_builtin
from .errors import ModelError

NAMESPACE_PATTERN = r"^[^\s.\x00-\x1f\x7f]+(?:\.[^\s.\x00-\x1f\x7f]+)+(?![\s\S])"
METADATA_FIELDS = ("extensions", "provenance", "display_id")


def extensions_schema():
    return {"type": "object", "propertyNames": {"type": "string", "pattern": NAMESPACE_PATTERN}}


def provenance_schema():
    text = {"$ref": "#/$defs/text"}
    source = {"type": "string", "pattern": r"^[A-Z][A-Z0-9]{1,7}-SRC-(?:[0-7][0-9A-HJKMNP-TV-Z]{25}|[0-9]{4})(?![\s\S])"}
    return {"type": "array", "items": {
        "type": "object", "required": ["captured_at"],
        "properties": {"source_id": source, "locator": dict(text),
                       "captured_at": {"$ref": "#/$defs/utc"},
                       "excerpt": dict(text), "content_sha256": {
                           "type": "string", "pattern": r"^[0-9a-f]{64}(?![\s\S])"},
                       "extensions": extensions_schema()},
        "allOf": [{"anyOf": [{"required": ["source_id"]}, {"required": ["locator"]}]},
                  {"anyOf": [{"required": ["excerpt"]}, {"required": ["content_sha256"]}]}],
        "additionalProperties": False}}


def metadata_schemas():
    return {"extensions": extensions_schema(), "provenance": provenance_schema(),
            "display_id": {"$ref": "#/$defs/text"}}


def validate_extensions(value, *, pointer="/extensions"):
    """Check namespace syntax only, preserving arbitrary JSON value semantics."""
    try:
        validate_builtin(value, extensions_schema())
    except ModelError as error:
        error.pointer = pointer + error.pointer
        raise
