"""Typed equality and ordering of explicit SRX values; no locale or casts."""

from ._json_values import JsonSnapshot, json_type
from .types import MISSING
from .errors import SrxError

COMPARISONS = ("eq", "ne", "lt", "lte", "gt", "gte")


def _equal(left, right):
    """Strict deep JSON equality, after full validation of both operands."""
    kind = json_type(left)
    if kind != json_type(right):
        return False
    if kind == "array":
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right))
    if kind == "object":
        return left.keys() == right.keys() and all(_equal(left[key], right[key]) for key in sorted(left))
    return left == right


def compare(op, left, right, *, rule_id, pointer="/expression"):
    """Missing has defined comparison results; incompatible top-level kinds fail.

    Nested type differences in arrays/objects mean unequal JSON values, not a
    Python-style True==1 match. Operand snapshots reject foreign conversion hooks.
    """
    if type(op) is not str or op not in COMPARISONS:
        raise SrxError("unsupported_comparison", rule_id=rule_id, pointer=pointer+"/op",
                       expected="comparison operator", actual=json_type(op))
    left = left if left is MISSING else JsonSnapshot(left, rule_id=rule_id, pointer=pointer+"/args/0").data
    right = right if right is MISSING else JsonSnapshot(right, rule_id=rule_id, pointer=pointer+"/args/1").data
    if left is MISSING or right is MISSING:
        return op == "ne"
    kind = json_type(left)
    if kind != json_type(right):
        raise SrxError("operand_types", rule_id=rule_id, pointer=pointer+"/args/1",
                       expected=kind, actual=json_type(right))
    if op == "eq":
        return _equal(left, right)
    if op == "ne":
        return not _equal(left, right)
    if kind not in ("number", "string"):
        raise SrxError("operand_type", rule_id=rule_id, pointer=pointer+"/args/0",
                       expected="number or string", actual=kind)
    if op == "lt":
        return left < right
    if op == "lte":
        return left <= right
    if op == "gt":
        return left > right
    return left >= right
