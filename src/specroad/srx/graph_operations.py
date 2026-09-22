"""Direct operations and bounded iterative BFS over the already loaded graph."""

from collections import deque
from .graph_access import GraphReadContext
from .types import require_type


def direct_graph_operation(node, roots, *, graph, rule_id, at):
    access = GraphReadContext(node, roots, graph=graph, rule_id=rule_id, at=at)
    op = node["op"]
    views = access.neighbours(access.start)
    if op == "has_relation":
        return any(("target_id" not in node or view.target.id == node["target_id"])
                   and ("target_type" not in node or view.target.artifact_type == node["target_type"])
                   for view in views)
    return len({view.relation_id for view in views})


class ReachabilityIteration:
    """One search cursor per expression; the AST machine schedules predicates."""
    def __init__(self, node, roots, *, graph, rule_id, at):
        self.access = GraphReadContext(node, roots, graph=graph, rule_id=rule_id, at=at)
        start = self.access.start
        self.node = node
        self.rule_id = rule_id
        self.at = at
        self.queue = deque([(start, 0)])
        self.seen = {start}
        self.current = None
        self.result = False

    @property
    def done(self):
        return self.result or not self.queue

    def next_roots(self):
        self.current = self.queue.popleft()
        return self.access.candidate_roots(self.current[0])

    def accept(self, result):
        require_type(result, ("boolean",), rule_id=self.rule_id, pointer=self.at+"/where")
        if result:
            self.result = True
            self.queue.clear()
            return
        identifier, depth = self.current
        if depth < self.node["max_depth"]:
            for view in self.access.neighbours(identifier):
                target = view.target.id
                if target not in self.seen:
                    self.seen.add(target)
                    self.queue.append((target, depth+1))
