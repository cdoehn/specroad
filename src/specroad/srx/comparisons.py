"""Typed equality and ordering of explicit SRX values; no locale or casts."""

from operator import lt, le, gt, ge
from types import MappingProxyType
from ._json_values import JsonSnapshot, json_type
from .types import MISSING
from .errors import SrxError

COMPARISONS = ("eq", "ne", "lt", "lte", "gt", "gte")
_ORDER = MappingProxyType({"lt": lt, "lte": le, "gt": gt, "gte": ge})


def _equal(left, right):
    """Iterative deep JSON equality; keys visited in stable codepoint order."""
    work = [(left, right)]
    while work:
        left, right = work.pop()
        kind = json_type(left)
        if kind != json_type(right):
            return False
        if kind == "array":
            if len(left) != len(right):
                return False
            work.extend(reversed(tuple(zip(left, right))))
        elif kind == "object":
            if left.keys() != right.keys():
                return False
            work.extend((left[key], right[key]) for key in sorted(left, reverse=True))
        elif left != right:
            return False
    return True


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
    if op in ("eq", "ne"):
        equal = _equal(left, right)
        return equal if op == "eq" else not equal
    if kind not in ("number", "string"):
        raise SrxError("operand_type", rule_id=rule_id, pointer=pointer+"/args/0",
                       expected="number or string", actual=kind)
    return _ORDER[op](left, right)
