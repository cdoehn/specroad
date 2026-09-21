"""Own SRX input fixtures: no file or process state."""
from specroad.srx import SrxProgram, EvaluationContext, evaluate


def literal(value):
    return {"op": "literal", "value": value}


def field(pointer="", context="artifact"):
    return {"op": "field", "context": context, "pointer": pointer}


def expression_document(node):
    return {"language": "srx", "version": "1.0", "expression": node}


def roots(artifact=None):
    return {"artifact": {} if artifact is None else artifact, "configuration": None,
            "project": {}, "relations": []}


def run(node, artifact=None, context=None):
    return evaluate(SrxProgram(expression_document(node), rule_id="rule-test"),
                    EvaluationContext(roots(artifact) if context is None else context, rule_id="rule-test"))


def binary(op, left, right):
    return {"op": op, "args": [left, right]}
