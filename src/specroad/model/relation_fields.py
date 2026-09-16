"""Passive relation identity schema, independent of entropy and inventories."""

from .relation_values import RANDOM_SCHEME, DERIVED_SCHEME


def relation_identity_fields():
    """Partial field assertions; the full relation/graph schema is a later layer.

    Absence of BOTH fields is allowed in the existing common-only projection.
    Supplying either requires both. This is never full relation validation.
    """
    return {
        "type": "object",
        "properties": {
            "relation_id": {"type": "string", "pattern": r"^REL-[0-7][0-9A-HJKMNP-TV-Z]{25}(?![\s\S])"},
            "id_scheme": {"enum": [RANDOM_SCHEME, DERIVED_SCHEME]},
        },
        "anyOf": [
            {"required": ["relation_id", "id_scheme"]},
            {"not": {"anyOf": [{"required": ["relation_id"]}, {"required": ["id_scheme"]}]}},
        ],
    }
