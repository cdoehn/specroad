"""Immutable, canonical schema values shared by retrieval and field validation."""
from dataclasses import dataclass
import hashlib
import json
import re

from .canonical import canonical_json_bytes
from .errors import ModelError
from .schema_identity import CATEGORIES, DIALECT, identity_metadata


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
        if (type(self.schema_id) is not str or not self.schema_id or
                type(self.version) is not str or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", self.version) is None or
                self.category not in CATEGORIES or self.stability != "experimental" or
                type(self.validation_scope) is not str or not self.validation_scope or
                type(self._encoded) is not bytes):
            raise SchemaLookupError("invalid_schema_resource")
        expected = identity_metadata(self.schema_id)
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

    def validate(self, value):
        """Apply these exact captured field assertions, never semantic approval."""
        from ._schema import validate_builtin
        validate_builtin(value, self.schema)

