"""SRX sequence operations over explicitly evaluated values; no locale or casts."""

from ._sequence_values import membership, size, string_pair
from .types import require_type
from ._json_values import json_type
from .errors import SrxError

COLLECTION_OPERATORS = ("in", "contains", "starts_with", "ends_with", "length", "count")


def collection_operation(op, operands, *, rule_id, pointer="/expression"):
    """Complete a validated operation; search follows the existing strict eq.

    Missing as a searched value inherits eq's false result. Missing as a container
    is a type error. Comparison errors are not converted into nonmatching items.
    """
    if op in ("length", "count"):
        return size(operands[0], array_only=op == "count", rule_id=rule_id, pointer=pointer)
    left, right = operands
    if op == "in":
        require_type(right, ("array",), rule_id=rule_id, pointer=pointer+"/args/1")
        return membership(left, right, rule_id=rule_id, pointer=pointer)
    if op == "contains":
        require_type(left, ("string", "array"), rule_id=rule_id, pointer=pointer+"/args/0")
        if json_type(left) == "array":
            return membership(right, left, rule_id=rule_id, pointer=pointer)
        require_type(right, ("string",), rule_id=rule_id, pointer=pointer+"/args/1")
        return right in left
    if op in ("starts_with", "ends_with"):
        left, right = string_pair(left, right, rule_id=rule_id, pointer=pointer)
        return left.startswith(right) if op == "starts_with" else left.endswith(right)
    raise SrxError("unsupported_operator", rule_id=rule_id, pointer=pointer+"/op",
                   expected="collection operator", actual=json_type(op))
