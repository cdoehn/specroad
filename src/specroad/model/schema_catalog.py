"""Project-free schema discovery for the actually implemented distribution.

No path/URL is treated as a source. Every identifier selects a trusted factory.
The exported resource is the resource used by that schema's field validator.
Semantic postchecks and future format implementations are not implied by it.
"""
from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType
import re

from .artifact_types import artifact_types
from .artifact_schemas import artifact_common_schema
from .domain_schemas import DOMAIN_TYPES, domain_schema
from .record_schemas import RECORD_TYPES, record_schema
from .configuration_schema import SCHEMA_ID, configuration_json_schema
from .versions import SCHEMA_VERSION
from .canonical import canonical_json_bytes
from .errors import ModelError

CATALOG_VERSION = "1.0.0"


class SchemaLookupError(ModelError):
    def __init__(self, reason="unknown_schema_id"):
        super().__init__(reason)


@dataclass(frozen=True)
class SchemaResource:
    schema_id: str
    version: str
    category: str
    validation_scope: str
    _encoded: bytes
    stability: str = "experimental"

    def __post_init__(self):
        from ._schema import _check_vocabulary
        from ..cli.result_schemas import CATEGORIES, DIALECT
        if (type(self.schema_id) is not str or not self.schema_id or
                type(self.version) is not str or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", self.version) is None or
                self.category not in CATEGORIES or self.stability != "experimental" or
                type(self.validation_scope) is not str or not self.validation_scope or
                type(self._encoded) is not bytes):
            raise SchemaLookupError("invalid_schema_resource")
        from ..cli.result_schemas import RESULT_IDS
        if self.schema_id in RESULT_IDS:
            expected = ("2.0.0" if self.schema_id == "json-envelope-v2" else "1.0.0",
                "exchange" if self.schema_id == "sarif-specroad-v1" else "result",
                "sarif_projection_only" if self.schema_id == "sarif-specroad-v1" else "result_fields_only")
        else:
            parts = self.schema_id.split(":", 4)
            if len(parts) != 5 or parts[:3] != ["urn", "specroad", "schema"]:
                raise SchemaLookupError("invalid_schema_resource")
            category_scopes = {"artifact-common": ("artifact", "common_fields_only"),
                "artifact-domain": ("artifact", "domain_fields_only"),
                "artifact-record": ("artifact", "record_fields_only"),
                "project-configuration": ("configuration", "configuration_fields_only"),
                "request": ("request", "request_fields_only")}
            family = parts[4].split(":", 1)[0]
            if family not in category_scopes:
                raise SchemaLookupError("invalid_schema_resource")
            expected = (parts[3], *category_scopes[family])
        if (self.version, self.category, self.validation_scope) != expected:
            raise SchemaLookupError("invalid_schema_resource")
        try:
            schema = json.loads(self._encoded)
            if (type(schema) is not dict or schema.get("$id") != self.schema_id or
                    schema.get("$schema") != DIALECT or
                    schema.get("x-specroad-validation-scope") != self.validation_scope or
                    canonical_json_bytes(schema) != self._encoded):
                raise ValueError("inconsistent resource")
            _check_vocabulary(schema)
        except (ValueError, TypeError, RecursionError, ModelError) as error:
            raise SchemaLookupError("invalid_schema_resource") from error

    @classmethod
    def capture(cls, document, version, category):
        if type(document) is not dict or not {"$id", "x-specroad-validation-scope"} <= document.keys():
            raise SchemaLookupError("invalid_schema_resource")
        try:
            encoded = canonical_json_bytes(document)
        except (ValueError, TypeError, RecursionError, ModelError) as error:
            raise SchemaLookupError("invalid_schema_resource") from error
        return cls(document["$id"], version, category,
                   document["x-specroad-validation-scope"], encoded)

    @property
    def schema(self):
        return json.loads(self._encoded)

    def metadata(self):
        return {"schema_id": self.schema_id, "version": self.version, "stability": self.stability,
                "category": self.category, "validation_scope": self.validation_scope,
                "sha256": hashlib.sha256(self._encoded).hexdigest()}


class SchemaCatalog:
    def __init__(self, registry=None):
        from ..cli.commands import builtin_registry
        from ..cli.result_schemas import RESULT_IDS
        self._registry = builtin_registry() if registry is None else registry
        providers = {}
        for entry in artifact_types():
            providers[entry.schema_id] = ("artifact", SCHEMA_VERSION, "common", entry.artifact_type)
        for kind in DOMAIN_TYPES:
            providers["urn:specroad:schema:" + SCHEMA_VERSION + ":artifact-domain:" + kind] = ("artifact", SCHEMA_VERSION, "domain", kind)
        for kind in RECORD_TYPES:
            providers["urn:specroad:schema:" + SCHEMA_VERSION + ":artifact-record:" + kind] = ("artifact", SCHEMA_VERSION, "record", kind)
        providers[SCHEMA_ID] = ("configuration", SCHEMA_VERSION, "configuration", None)
        for schema_id in RESULT_IDS:
            providers[schema_id] = ("exchange" if schema_id == "sarif-specroad-v1" else "result",
                "2.0.0" if schema_id == "json-envelope-v2" else "1.0.0", "result", schema_id)
        for command in self._registry.commands:
            schema_id = "urn:specroad:schema:1.0.0:request:" + command.command_id
            providers[schema_id] = ("request", "1.0.0", "request", command.command_id)
        self._providers = MappingProxyType(providers)

    def get(self, schema_id):
        if type(schema_id) is not str or schema_id not in self._providers:
            raise SchemaLookupError()
        category, version, family, key = self._providers[schema_id]
        if family == "common": document = artifact_common_schema(key)
        elif family == "domain": document = domain_schema(key)
        elif family == "record": document = record_schema(key)
        elif family == "configuration": document = configuration_json_schema()
        elif family == "result":
            from ..cli.result_schemas import result_json_schema
            document = result_json_schema(key)
        else:
            from ..cli.request_schema import request_schema
            document = request_schema(self._registry.resolve(key))
        if document.get("$id") != schema_id:
            raise SchemaLookupError("schema_identity_mismatch")
        return SchemaResource.capture(document, version, category)

    def list(self):
        from ..cli.result_schemas import CATEGORIES
        rows = [self.get(name).metadata() for name in sorted(self._providers)]
        return {"format_version": CATALOG_VERSION, "schemas": rows,
                "categories": {category: sum(row["category"] == category for row in rows) for category in CATEGORIES}}

    def show(self, schema_id):
        resource = self.get(schema_id)
        return {"format_version": CATALOG_VERSION, "metadata": resource.metadata(), "schema": resource.schema}

    def validate(self, schema_id, value):
        from ._schema import validate_builtin
        # Only structural assertions; never a project/lifecycle authorization.
        validate_builtin(value, self.get(schema_id).schema)
