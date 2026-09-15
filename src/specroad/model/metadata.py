"""Validation adapter for passive extension data, never an execution registry."""

from ._schema import validate_builtin
from .errors import ModelError
from .metadata_fields import (METADATA_FIELDS, NAMESPACE_PATTERN, extensions_schema,
                              metadata_schemas, provenance_schema)

def validate_extensions(value, *, pointer="/extensions"):
    """Check namespace syntax only, preserving arbitrary JSON value semantics."""
    try:
        validate_builtin(value, extensions_schema())
    except ModelError as error:
        error.pointer = pointer + error.pointer
        raise
