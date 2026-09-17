"""Project-free catalog and exact retrieval of implemented field contracts.

Semantic postchecks and future formats are not implied by a schema. Lookup is
never a path/URL resolver. Owning validators and catalog share trusted factories.
"""
from .schema_identity import CATALOG_VERSION, CATEGORIES
from .schema_resource import SchemaLookupError, SchemaResource
from .schema_sources import provider_document, providers_for


class SchemaCatalog:
    def __init__(self, registry=None):
        from ..cli.commands import builtin_registry
        self._registry = builtin_registry() if registry is None else registry
        self._providers = providers_for(self._registry)

    def get(self, schema_id):
        if type(schema_id) is not str or schema_id not in self._providers:
            raise SchemaLookupError()
        provider = self._providers[schema_id]
        document = provider_document(provider, self._registry)
        if document.get("$id") != schema_id:
            raise SchemaLookupError("schema_identity_mismatch")
        return SchemaResource.capture(document, provider.version, provider.category)

    def list(self):
        rows = [self.get(name).metadata() for name in sorted(self._providers)]
        return {"format_version": CATALOG_VERSION, "schemas": rows,
                "categories": {category: sum(row["category"] == category for row in rows) for category in CATEGORIES}}

    def show(self, schema_id):
        resource = self.get(schema_id)
        return {"format_version": CATALOG_VERSION, "metadata": resource.metadata(), "schema": resource.schema}

    def validate(self, schema_id, value):
        self.get(schema_id).validate(value)
