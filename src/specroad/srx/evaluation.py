"""Evaluation of the enabled literal operator on trusted frozen values."""

from .program import SrxProgram
from .context import EvaluationContext
from .errors import SrxError

def evaluate(program, context):
    """Return a new JSON value, without Boolean coercion or external lookup."""
    if type(program) is not SrxProgram:
        raise SrxError("program_required", rule_id=None, expected="SrxProgram", actual="non_program")
    if type(context) is not EvaluationContext:
        raise SrxError("context_required", rule_id=program.rule_id,
                       expected="EvaluationContext", actual="non_context", subject="context")
    return program.value


