"""Pure operator completion; no scheduler, I/O, implicit casts or AST mutation."""

from . import fields
from .comparisons import compare
from .types import MISSING, require_type


def boolean_value(value, *, rule_id, at):
    return require_type(value, ("boolean",), rule_id=rule_id, pointer=at)


def apply_values(op, operands, *, rule_id, at):
    if op == "exists":
        return operands[0] is not MISSING
    if op == "not":
        return not boolean_value(operands[0], rule_id=rule_id, at=at+"/arg")
    return compare(op, operands[0], operands[1], rule_id=rule_id, pointer=at)


def leaf_value(node, roots, *, rule_id, at):
    if node["op"] == "literal":
        return node["value"]
    name, tokens = fields.checked_selector(node["context"], node["pointer"], rule_id=rule_id, at=at)
    return fields.resolve_tokens(roots[name], tokens, rule_id=rule_id, at=at+"/pointer")
