"""Small read-only, expression-local view onto an explicitly supplied graph."""

from dataclasses import dataclass
from .graph import require_graph


@dataclass(frozen=True, init=False)
class GraphReadContext:
    """Bind root, direction and type selection once; never resolve external data.

    All AST/context inputs belong to this evaluation. A nested operator obtains
    a new access context, so it cannot replace a parent's root or selectors.
    """
    graph: object
    roots: object
    start: str
    direction: str
    types: object
    rule_id: str
    meter: object
    at: str

    def __init__(self, node, roots, *, graph, rule_id, at, meter=None):
        object.__setattr__(self, "meter", meter)
        object.__setattr__(self, "at", at)
        graph = require_graph(graph, rule_id=rule_id, at=at)
        start = graph.checked_start(roots, rule_id=rule_id, at=at)
        direction = "incoming" if node["op"] == "incoming_count" else node["direction"]
        selected = node["types"]
        object.__setattr__(self, "graph", graph)
        object.__setattr__(self, "roots", roots)
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "types", "*" if selected == "*" else tuple(selected))
        object.__setattr__(self, "rule_id", rule_id)

    def neighbours(self, identifier):
        return self.graph.neighbours(identifier, self.direction, self.types, meter=self.meter, pointer=self.at)

    def candidate_roots(self, identifier):
        return self.graph.candidate_roots(self.roots, identifier, rule_id=self.rule_id, meter=self.meter, pointer=self.at)
