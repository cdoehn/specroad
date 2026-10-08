"""Distribution schema identities and metadata; not user-defined registration."""

DIALECT = "https://json-schema.org/draft/2020-12/schema"
CATALOG_VERSION = "1.0.0"
CATEGORIES = ("artifact", "configuration", "mapping", "result", "exchange", "request")
ENVELOPE_ID = "json-envelope-v2"
RESULT_IDS = (ENVELOPE_ID, "help-v1", "version-info-v1", "command-description-v1",
              "capabilities-v1", "schema-catalog-v1", "schema-document-v1", "sarif-specroad-v1", "environment-v1")
CHANGE_PLAN_VERSION = "1.2.0"
CHANGE_PLAN_FAMILY = "change-plan"
CHANGE_PLAN_ID = "urn:specroad:schema:" + CHANGE_PLAN_VERSION + ":" + CHANGE_PLAN_FAMILY
CHANGE_PLAN_SCOPE = "change_plan_fields_only"


def identity_metadata(schema_id):
    """Return (version, category, scope), or None for an unknown ID family.

    Knowing a family never registers a schema. Exact availability is exclusively
    determined by the trusted distribution provider index.
    """
    if schema_id in RESULT_IDS:
        return ("2.0.0" if schema_id == ENVELOPE_ID else "1.0.0",
                "exchange" if schema_id == "sarif-specroad-v1" else "result",
                "sarif_projection_only" if schema_id == "sarif-specroad-v1" else "result_fields_only")
    parts = schema_id.split(":", 4)
    if len(parts) != 5 or parts[:3] != ["urn", "specroad", "schema"]:
        return None
    category_scopes = {"artifact-common": ("artifact", "common_fields_only"),
        "artifact-domain": ("artifact", "domain_fields_only"),
        "artifact-record": ("artifact", "record_fields_only"),
        "project-configuration": ("configuration", "configuration_fields_only"),
        CHANGE_PLAN_FAMILY: ("exchange", CHANGE_PLAN_SCOPE),
        "request": ("request", "request_fields_only")}
    family = parts[4].split(":", 1)[0]
    if family not in category_scopes:
        return None
    return (parts[3], *category_scopes[family])
