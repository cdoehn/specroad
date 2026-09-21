"""Iterative evaluation of literals, static fields and existence tests."""

from .program import SrxProgram
from .context import EvaluationContext
from .errors import SrxError
from .fields import checked_selector, resolve_tokens
from .types import MISSING


def evaluate(program, context):
    """Return an independent JSON value or the nonserializable Missing sentinel."""
    if type(program) is not SrxProgram:
        raise SrxError("program_required", rule_id=None, expected="SrxProgram", actual="non_program")
    if type(context) is not EvaluationContext:
        raise SrxError("context_required", rule_id=program.rule_id,
                       expected="EvaluationContext", actual="non_context", subject="context")
    roots = context.data
    work = [("visit", program.expression, "/expression")]
    values = []
    while work:
        action, node, at = work.pop()
        if action == "exists":
            values.append(values.pop() is not MISSING)
            continue
        op = node["op"]
        if op == "literal":
            values.append(node["value"])
        elif op == "field":
            name, tokens = checked_selector(node["context"], node["pointer"], rule_id=program.rule_id, at=at)
            values.append(resolve_tokens(roots[name], tokens,
                                         rule_id=program.rule_id, at=at+"/pointer"))
        else:
            work.append(("exists", None, at))
            work.append(("visit", node["arg"], at+"/arg"))
    return values[0]
