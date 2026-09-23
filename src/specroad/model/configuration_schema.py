"""Inspectable schema for existing configuration field checks, not path policy.

Filesystem classification, overlaps, execution policy and binding checks remain
in validate_configuration. Exporting this schema does not grant write access.
"""
from .versions import SCHEMA_VERSION
from .metadata_fields import extensions_schema

SCHEMA_ID = "urn:specroad:schema:" + SCHEMA_VERSION + ":project-configuration"


def configuration_json_schema():
    from .configuration import REQUIRED_FIELDS, OPTIONAL_FIELDS
    from .language_policy import language_policy_schema
    text = {"type": "string", "minLength": 1, "pattern": r"^(?=[\s\S]*\S)(?![\s\S]*\x00)"}
    versioned = {"type": "string", "pattern": r"^[A-Za-z0-9][A-Za-z0-9_.-]*@[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?(?:\+[A-Za-z0-9.-]+)?(?![\s\S])"}
    def obj(fields):
        return {"type": "object", "properties": fields, "additionalProperties": False}
    fields = {name: {"type": "object"} for name in OPTIONAL_FIELDS}
    fields.update({
        "schema_version": {"const": SCHEMA_VERSION},
        "project_id": dict(text), "project_name": dict(text), "default_locale": dict(text),
        "id_prefix": {"type": "string", "pattern": r"^[A-Z][A-Z0-9]{1,7}(?![\s\S])"},
        "managed_paths": {"type": "array", "items": dict(text)},
        "generated_path": dict(text),
        "profiles": {"type": "array", "items": versioned},
        "language_packages": {"type": "array", "items": versioned},
        "language_policy": language_policy_schema(),
        "validation_policy": obj({"fail_on": {"enum": ["info", "warning", "error"]},
            "minimum_human_proposal_approvals": {"type": "integer", "minimum": 1, "default": 1},
            "required_relation_review": {"const": "current"}}),
        "transaction_policy": obj({"auto_recover": {"type": "boolean"}, "retain_receipts": {"const": True, "default": True}}),
        "srx_policy": obj({"numeric_policy_version": {"const": "srx-decimal-v1", "default": "srx-decimal-v1"},
            "decimal_precision": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 34}}),
        "resource_limits": {"type": "object", "additionalProperties": {"type": "integer", "minimum": 0}},
        "extensions": extensions_schema(),
        "language_registry": {**obj({"registry_id": {"const": "iana-language-subtags"},
            "registry_version": {"type": "string", "format": "date"}, "path": dict(text),
            "sha256": {"type": "string", "pattern": r"^[0-9a-f]{64}(?![\s\S])"}}),
            "required": ["registry_id", "registry_version", "path", "sha256"]},
    })
    assert set(fields) == REQUIRED_FIELDS | OPTIONAL_FIELDS
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": SCHEMA_ID,
        "description": "Project configuration field contract; paths, duplicate bindings and safety policy require the Core validator.",
        "x-specroad-validation-scope": "configuration_fields_only",
        "type": "object", "required": sorted(REQUIRED_FIELDS), "properties": fields,
        "additionalProperties": False}
