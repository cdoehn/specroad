"""Internal exact field-shape builders shared by stored record contracts."""
from ._schema import validate_builtin
from .domain_fields import reference_schema


def _object(properties, required=None):
    return {"type": "object", "required": list(properties if required is None else required),
            "properties": properties, "additionalProperties": False}



def _array(items, *, nonempty=False):
    return {"type": "array", "items": items, "minItems": int(nonempty)}



def _typed_reference(value, prefixes):
    validate_builtin(value, {"anyOf": [reference_schema(prefix) for prefix in prefixes]})
