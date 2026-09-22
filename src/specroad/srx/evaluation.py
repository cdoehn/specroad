"""Public evaluation with optional deterministic work observations, never I/O."""
from dataclasses import dataclass
from .program import SrxProgram
from .context import EvaluationContext
from .errors import SrxError
from ._machine import evaluate_expression
from ._json_values import JsonSnapshot
from .types import MISSING
from ._resource_accounting import WorkMeter
from .resource_observations import ResourceUsage
from .validation import _validate_document


@dataclass(frozen=True, init=False)
class EvaluationObservation:
    """Owned value plus deterministic counters, not a persisted work checkpoint."""
    _snapshot: object
    usage: object

    def __init__(self, value, usage, *, rule_id):
        if type(usage) is not ResourceUsage or usage.evaluation_completed is not True:
            raise ValueError("A completed usage observation is required")
        snapshot = None if value is MISSING else JsonSnapshot(value, rule_id=rule_id, subject="result")
        object.__setattr__(self, "_snapshot", snapshot)
        object.__setattr__(self, "usage", usage)

    @property
    def value(self):
        return MISSING if self._snapshot is None else self._snapshot.data


def _run(program, context):
    if type(program) is not SrxProgram:
        raise SrxError("program_required", rule_id=None, expected="SrxProgram", actual="non_program")
    if type(context) is not EvaluationContext:
        raise SrxError("context_required", rule_id=program.rule_id,
                       expected="EvaluationContext", actual="non_context", subject="context")
    document = program.document
    # A reused program cannot bypass the CURRENT explicit project safety policy.
    structure = _validate_document(document, program.rule_id,
                                   structure_limits=context.resource_policy.structure)
    meter = WorkMeter(context.resource_policy, structure)
    try:
        value = evaluate_expression(document["expression"], context.data, rule_id=program.rule_id,
                                    graph=context.graph, numeric_policy=context.numeric_policy, meter=meter)
    except SrxError as error:
        # Keep the original numeric/type/graph diagnostic. A prior soft event
        # cannot turn a real failure into false, success or ready-to-resume.
        error.resource_usage = meter.observation(False)
        raise
    return value, meter.observation(True)


def evaluate(program, context):
    """Compatible value-only API; never emit console text or coerce a Boolean."""
    return _run(program, context)[0]


def evaluate_with_usage(program, context):
    """Return owned result and work observations; soft targets never truncate it."""
    value, usage = _run(program, context)
    return EvaluationObservation(value, usage, rule_id=program.rule_id)
