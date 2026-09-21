"""Reusable typed sequence primitives; operands are explicit, never host data."""

from .comparisons import compare
from .types import require_type


def size(value, *, array_only, rule_id, pointer):
    allowed = ("array",) if array_only else ("string", "array", "object")
    return len(require_type(value, allowed, rule_id=rule_id, pointer=pointer+"/arg"))


def membership(needle, values, *, rule_id, pointer):
    # Reuse precisely the same strict equality and Missing behavior as eq.
    for item in values:
        if compare("eq", needle, item, rule_id=rule_id, pointer=pointer):
            return True
    return False


def string_pair(left, right, *, rule_id, pointer):
    require_type(left, ("string",), rule_id=rule_id, pointer=pointer+"/args/0")
    require_type(right, ("string",), rule_id=rule_id, pointer=pointer+"/args/1")
    return left, right
