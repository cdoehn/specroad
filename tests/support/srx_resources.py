"""Explicit, owned SRX resource inputs; no clocks or external work adapters."""
from specroad.srx import SrxProgram, EvaluationContext, evaluate_with_usage
from .srx import roots, expression_document


def observed(node, *, limits=None, artifact=None, graph=None, structure_limits=None):
    data = roots(artifact)
    data['project']['resource_limits'] = {} if limits is None else dict(limits)
    context = EvaluationContext(data, rule_id='resource-rule', graph=graph)
    program = SrxProgram(expression_document(node), rule_id='resource-rule', structure_limits=structure_limits)
    return evaluate_with_usage(program, context)
