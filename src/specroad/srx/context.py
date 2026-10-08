"""Immutable explicitly supplied evaluation context; no loaders or defaults."""

from dataclasses import dataclass
from ._json_values import JsonSnapshot
from .numeric_policy import NumericPolicy
from .resources import ResourcePolicy
from .validation import _rule_id, _validate_context

@dataclass(frozen=True, init=False)
class EvaluationContext:
    """Only four explicit roots; profiles/statistics are passive project data.

    configuration=None explicitly means no selected configuration. No defaults
    or host environment are consulted. item is lexically bound only in quantifier predicates
    and is never accepted as an external root. Relations are precomputed data,
    never a callable resolver. Field lookup reads only these supplied immutable roots.
    Optional runtime resource options select work policy outside all four roots;
    they cannot change field lookup, semantic depth or hard structural guards.
    """
    _snapshot: JsonSnapshot
    graph: object
    numeric_policy: NumericPolicy
    resource_policy: ResourcePolicy

    def __init__(self, document, *, rule_id, graph=None, resource_options=None):
        rule_id = _rule_id(rule_id)
        snapshot = JsonSnapshot(document, rule_id=rule_id, subject="context")
        data = snapshot.data
        _validate_context(data, rule_id)
        object.__setattr__(self, "numeric_policy", NumericPolicy.from_project(data["project"], rule_id=rule_id))
        object.__setattr__(self, "resource_policy", ResourcePolicy.from_project(
            data["project"], rule_id=rule_id, resource_options=resource_options))
        if graph is not None:
            from .graph import require_graph
            require_graph(graph, rule_id=rule_id, at="/graph")
        object.__setattr__(self, "graph", graph)
        object.__setattr__(self, "_snapshot", snapshot)

    @property
    def data(self):
        return self._snapshot.data


