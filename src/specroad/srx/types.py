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


VALUE_TYPES = ("missing", "null", "boolean", "number", "string", "array", "object")


def require_type(value, allowed, *, rule_id, pointer="/expression"):
    """Operator type boundary with no truthiness, cast or value disclosure."""
    from .errors import SrxError
    if (type(allowed) is not tuple or not allowed
            or any(type(name) is not str or name not in VALUE_TYPES for name in allowed)):
        raise SrxError("invalid_type_signature", rule_id=rule_id, pointer=pointer,
                       expected="explicit SRX type tuple", actual="invalid_signature")
    actual = value_type(value, rule_id=rule_id)
    if actual not in allowed:
        raise SrxError("operand_type", rule_id=rule_id, pointer=pointer,
                       expected=" or ".join(allowed), actual=actual)
    return value
