"""Owned complete loaded-graph fixtures, with no filesystem or live resolver."""
from specroad.graph.relations import SourceRelations
from specroad.srx import EvaluationContext, LoadedGraph, SrxProgram, evaluate
from .artifacts import artifact_bytes
from .relations import artifact, edge, aid
from .srx import expression_document, roots, field, binary, literal


def records(values):
    return tuple(SourceRelations(artifact_bytes(value)) for value in values)


def graph(values):
    return LoadedGraph(records(values), rule_id="graph-test")


def call(node, values, start=0, *, extra_roots=None):
    data = roots(values[start])
    if extra_roots:
        data.update(extra_roots)
    return evaluate(SrxProgram(expression_document(node), rule_id="graph-test"),
                    EvaluationContext(data, graph=graph(values), rule_id="graph-test"))


def count(types="*", direction="outgoing"):
    return {"op": "relation_count", "direction": direction, "types": types}


def incoming(types="*"):
    return {"op": "incoming_count", "types": types}


def has(types="*", direction="outgoing", **filters):
    return {"op": "has_relation", "direction": direction, "types": types, **filters}


def reach(target=None, depth=1, direction="outgoing", types="*", where=None):
    return {"op": "reachable", "direction": direction, "types": types, "max_depth": depth,
            "where": where if where is not None else binary("eq", field("/id"), literal(target))}


def chain():
    return [artifact(number=1, relations=[edge("depends_on", aid(number=2), number=1)]),
            artifact(number=2, relations=[edge("depends_on", aid(number=3), number=2)]),
            artifact(number=3)]
