"""Iterative SRX evaluation with ordered operands and Boolean short circuit."""

from .program import SrxProgram
from .context import EvaluationContext
from .errors import SrxError
from . import fields
from .types import MISSING, require_type
from .comparisons import compare, COMPARISONS


def evaluate(program, context):
    """Return an independent JSON value or Missing; never coerce to Boolean."""
    if type(program) is not SrxProgram:
        raise SrxError("program_required", rule_id=None, expected="SrxProgram", actual="non_program")
    if type(context) is not EvaluationContext:
        raise SrxError("context_required", rule_id=program.rule_id,
                       expected="EvaluationContext", actual="non_context", subject="context")
    roots = context.data
    rule_id = program.rule_id
    work = [("visit", program.expression, "/expression")]
    values = []
    while work:
        action, node, at = work.pop()
        if action == "unary":
            value = values.pop()
            if node == "exists":
                values.append(value is not MISSING)
            else:
                require_type(value, ("boolean",), rule_id=rule_id, pointer=at+"/arg")
                values.append(not value)
            continue
        if action == "binary":
            right = values.pop()
            left = values.pop()
            values.append(compare(node, left, right, rule_id=rule_id, pointer=at))
            continue
        if action == "boolean":
            op, args, index = node
            value = values.pop()
            require_type(value, ("boolean",), rule_id=rule_id, pointer=at+"/args/"+str(index))
            if (op == "and" and value is False) or (op == "or" and value is True):
                values.append(value)
            elif index + 1 == len(args):
                values.append(op == "and")
            else:
                work.append(("boolean", (op, args, index+1), at))
                work.append(("visit", args[index+1], at+"/args/"+str(index+1)))
            continue
        op = node["op"]
        if op == "literal":
            values.append(node["value"])
        elif op == "field":
            name, tokens = fields.checked_selector(node["context"], node["pointer"], rule_id=rule_id, at=at)
            values.append(fields.resolve_tokens(roots[name], tokens, rule_id=rule_id, at=at+"/pointer"))
        elif op in ("exists", "not"):
            work.append(("unary", op, at))
            work.append(("visit", node["arg"], at+"/arg"))
        elif op in COMPARISONS:
            work.append(("binary", op, at))
            work.append(("visit", node["args"][1], at+"/args/1"))
            work.append(("visit", node["args"][0], at+"/args/0"))
        elif op in ("and", "or"):
            args = node["args"]
            if not args:
                values.append(op == "and")
            else:
                work.append(("boolean", (op, args, 0), at))
                work.append(("visit", args[0], at+"/args/0"))
        else:
            raise SrxError("unsupported_operator", rule_id=rule_id, pointer=at+"/op",
                           expected="supported operator", actual="string")
    return values[0]
