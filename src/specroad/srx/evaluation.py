"""Public SRX entry boundary, separate from validated operator execution."""

from .program import SrxProgram
from .context import EvaluationContext
from .errors import SrxError
from ._machine import evaluate_expression


def evaluate(program, context):
    """Return an independent JSON value or Missing; never coerce to Boolean."""
    if type(program) is not SrxProgram:
        raise SrxError("program_required", rule_id=None, expected="SrxProgram", actual="non_program")
    if type(context) is not EvaluationContext:
        raise SrxError("context_required", rule_id=program.rule_id,
                       expected="EvaluationContext", actual="non_context", subject="context")
    roots = context.data
    return evaluate_expression(program.expression, roots, rule_id=program.rule_id, graph=context.graph)
