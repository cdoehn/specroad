"""Versioned common-field JSON Schema resources for the 28 Core artifact types.

These are explicitly COMMON-FIELD schemas, not complete artifact validation.
Type-specific fields, profile/graph rules and lifecycle authorization are later
layers. No caller may use this layer alone to approve or publish an artifact.
The resources are generated from trusted Python data so all Core distributions
ship the exact same schemas without optional data-file installation steps.
"""

from ._schema import validate_builtin
from .configuration import _json_values
from .versions import SCHEMA_VERSION
from .errors import ModelError
from .relation_identity import relation_identity_fields
from .metadata_fields import metadata_schemas, extensions_schema
from .artifact_types import ArtifactType, artifact_type, artifact_types

DIALECT = "https://json-schema.org/draft/2020-12/schema"
VALIDATION_SCOPE = "common_fields_only"
COMMON_REQUIRED = (
    "schema_version", "id", "id_scheme", "artifact_type", "title", "maturity",
    "revision", "created_at", "updated_at", "created_by", "updated_by", "relations", "extensions",
)
MATURITIES = ("draft", "proposed", "in_review", "approved", "rejected", "superseded", "retired")
LANGUAGE_REQUIRED = frozenset({"requirement", "document", "term"})

def _version(version):
    if type(version) is not str or version != SCHEMA_VERSION:
        raise ModelError("unsupported_schema_version", pointer="/schema_version",
                         highest_supported=SCHEMA_VERSION)


def _definitions():
    text = {"type": "string", "minLength": 1, "pattern": "\\S",
            "not": {"pattern": "\\u0000"}}
    actor = {"type": "object", "required": ["actor_type", "actor_id"],
             "properties": {"actor_type": {"enum": ["human", "ai", "ci", "tool"]},
                            "actor_id": dict(text)}, "additionalProperties": False}
    utc = {"type": "string", "format": "date-time",
           "pattern": r"^[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:[Zz]|\+00:00)(?![\s\S])"}
    return {"text": text, "actor": actor, "utc": utc}


def _properties(kind):
    text = {"$ref": "#/$defs/text"}
    actor = {"$ref": "#/$defs/actor"}
    return {
        "schema_version": {"const": SCHEMA_VERSION}, "id": dict(text),
        "id_scheme": {"enum": ["random128-v1", "legacy-sequential-v1"]},
        "artifact_type": {"const": kind}, "title": dict(text),
        "maturity": {"enum": list(MATURITIES)}, "revision": {"type": "integer", "minimum": 1},
        "created_at": {"$ref": "#/$defs/utc"}, "updated_at": {"$ref": "#/$defs/utc"},
        "created_by": dict(actor), "updated_by": dict(actor),
        "language": dict(text), "text_direction": {"enum": ["ltr", "rtl", "auto"]},
        "owner": {"anyOf": [dict(text), dict(actor)]},
        "tags": {"type": "array", "items": {"type": "string"}},
        "applicability": {"type": "object"},
        "relations": {"type": "array", "items": {
            "allOf": [relation_identity_fields()],
            "properties": {"extensions": extensions_schema()}}},
        "provenance": {"type": "array", "items": {"type": "object"}},
        "external_identities": {"type": "array", "items": {"type": "object"}},
        **metadata_schemas(),
    }


def artifact_common_schema(kind, version=SCHEMA_VERSION):
    """Return an independent, JSON-serializable Draft 2020-12 schema resource."""
    _version(version)
    item = artifact_type(kind)
    required = list(COMMON_REQUIRED)
    if kind in LANGUAGE_REQUIRED:
        required.append("language")
    # The schema binds the identity grammar to BOTH artifact kind and id_scheme.
    base = r"[A-Z][A-Z0-9]{1,7}-" + item.prefix + "-"
    branches = []
    for scheme, token in (("random128-v1", r"[0-7][0-9A-HJKMNP-TV-Z]{25}"),
                          ("legacy-sequential-v1", r"[0-9]{4}")):
        branches.append({"properties": {"id_scheme": {"const": scheme},
                           "id": {"type": "string", "pattern": "^(?:" + base + token + r")(?![\s\S])"}}})
    return {"$schema": DIALECT, "$id": item.schema_id,
            "$comment": "Common fields only. Never sufficient for approval, authoring or publication.",
            "x-specroad-validation-scope": VALIDATION_SCOPE,
            "type": "object", "required": required, "properties": _properties(kind),
            "$defs": _definitions(), "anyOf": branches, "additionalProperties": True}


def validate_common_fields(value, *, expected_type=None):
    """Check only the common layer, never infer a complete artifact or success."""
    if type(value) is not dict:
        raise ModelError("object_required")
    try:
        _json_values(value)
    except RecursionError as error:
        raise ModelError("unsupported_json_nesting") from error
    _version(value.get("schema_version"))
    item = artifact_type(value.get("artifact_type"))
    if expected_type is not None and item != artifact_type(expected_type):
        raise ModelError("artifact_type_mismatch", pointer="/artifact_type")
    try:
        validate_builtin(value, artifact_common_schema(item.artifact_type))
    except RecursionError as error:
        raise ModelError("unsupported_json_nesting") from error
