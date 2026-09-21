"""SRX value kinds; Missing is deliberately not a JSON value or a Boolean."""

from enum import Enum
from ._json_values import JsonSnapshot, json_type


class _Missing(Enum):
    TOKEN = object()

    def __bool__(self):
        raise TypeError("SRX missing has no implicit truth value")


MISSING = _Missing.TOKEN


def value_type(value, *, rule_id=None):
    """Classify a supported value without Python subclass/coercion shortcuts.

    Full validation prevents callers passing containers containing foreign objects,
    nonfinite numbers or Missing as though these were serializable JSON values.
    Integers and finite floats share Number; bool is never Number.
    """
    if value is MISSING:
        return "missing"
    JsonSnapshot(value, rule_id=rule_id)
    return json_type(value)
