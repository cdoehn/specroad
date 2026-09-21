"""SRX sequence operations over explicitly evaluated values; no locale or casts."""

from .comparisons import compare
from .types import require_type
from ._json_values import json_type
from .errors import SrxError

COLLECTION_OPERATORS = ("in", "contains", "starts_with", "ends_with", "length", "count")


def collection_operation(op, operands, *, rule_id, pointer="/expression"):
    """Complete a validated operation; membership uses the existing strict eq.

    The AST is already validated and owns its JSON operands. Missing as a searched
    value inherits eq's false result. Missing as a container is a type error.
    A comparison type error is never converted into a nonmatching element.
    """
    if op in ("length", "count"):
        allowed = ("array",) if op == "count" else ("string", "array", "object")
        value = require_type(operands[0], allowed, rule_id=rule_id, pointer=pointer+"/arg")
        return len(value)
    left, right = operands
    if op == "in":
        require_type(right, ("array",), rule_id=rule_id, pointer=pointer+"/args/1")
        for item in right:
            if compare("eq", left, item, rule_id=rule_id, pointer=pointer):
                return True
        return False
    if op == "contains":
        require_type(left, ("string", "array"), rule_id=rule_id, pointer=pointer+"/args/0")
        if json_type(left) == "string":
            require_type(right, ("string",), rule_id=rule_id, pointer=pointer+"/args/1")
            return right in left
        for item in left:
            if compare("eq", right, item, rule_id=rule_id, pointer=pointer):
                return True
        return False
    if op in ("starts_with", "ends_with"):
        require_type(left, ("string",), rule_id=rule_id, pointer=pointer+"/args/0")
        require_type(right, ("string",), rule_id=rule_id, pointer=pointer+"/args/1")
        return left.startswith(right) if op == "starts_with" else left.endswith(right)
    raise SrxError("unsupported_operator", rule_id=rule_id, pointer=pointer+"/op",
                   expected="collection operator", actual=json_type(op))
