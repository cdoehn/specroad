"""Bounded read-only SRX graph operations over an explicitly loaded graph."""

from collections import deque
from .graph import require_graph
from .types import require_type


def graph_operation(node, roots, *, graph, rule_id, at, item_scope, evaluate_predicate):
    graph = require_graph(graph, rule_id=rule_id, at=at)
    start = graph.checked_start(roots, rule_id=rule_id, at=at)
    op = node["op"]
    direction = "incoming" if op == "incoming_count" else node["direction"]
    if op != "reachable":
        views = graph.neighbours(start, direction, node["types"])
        if op == "has_relation":
            return any(("target_id" not in node or view.target.id == node["target_id"])
                       and ("target_type" not in node or view.target.artifact_type == node["target_type"])
                       for view in views)
        return len({view.relation_id for view in views})
    queue = deque([(start, 0)])
    seen = {start}
    while queue:
        identifier, depth = queue.popleft()
        candidate = graph.candidate_roots(roots, identifier, rule_id=rule_id)
        result = evaluate_predicate(node["where"], candidate, rule_id=rule_id,
                                    graph=graph, pointer=at+"/where", item_scope=item_scope)
        require_type(result, ("boolean",), rule_id=rule_id, pointer=at+"/where")
        if result:
            return True
        if depth < node["max_depth"]:
            for view in graph.neighbours(identifier, direction, node["types"]):
                target = view.target.id
                if target not in seen:
                    seen.add(target)
                    queue.append((target, depth+1))
    return False
