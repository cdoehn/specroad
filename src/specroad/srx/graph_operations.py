"""Direct operations and bounded iterative BFS over the already loaded graph."""

from collections import deque
from .graph_access import GraphReadContext
from .types import require_type
from ..runtime.control_points import complete_steps


def direct_graph_operation(node, roots, *, graph, rule_id, at, meter=None):
    return complete_steps(direct_graph_operation_steps(node, roots, graph=graph, rule_id=rule_id,
                                                       at=at, meter=meter))


def direct_graph_operation_steps(node, roots, *, graph, rule_id, at, meter=None, controls=None):
    access = GraphReadContext(node, roots, graph=graph, rule_id=rule_id, at=at, meter=meter)
    op = node["op"]
    views = yield from access.neighbours_steps(access.start, controls)
    if op == "has_relation":
        return any(("target_id" not in node or view.target.id == node["target_id"])
                   and ("target_type" not in node or view.target.artifact_type == node["target_type"])
                   for view in views)
    return len({view.relation_id for view in views})


class ReachabilityIteration:
    """One search cursor per expression; the AST machine schedules predicates."""
    def __init__(self, node, roots, *, graph, rule_id, at, meter=None):
        self.access = GraphReadContext(node, roots, graph=graph, rule_id=rule_id, at=at, meter=meter)
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
        return complete_steps(self.next_roots_steps())

    def next_roots_steps(self, controls=None):
        if self.access.meter is not None:
            self.access.meter.add("graph_steps", pointer=self.at)
        self.current = self.queue.popleft()
        if controls is not None:
            point = controls.advance('graph_steps')
            if point is not None:
                yield point
        return (yield from self.access.candidate_roots_steps(self.current[0], controls))

    def accept(self, result):
        return complete_steps(self.accept_steps(result))

    def accept_steps(self, result, controls=None):
        require_type(result, ("boolean",), rule_id=self.rule_id, pointer=self.at+"/where")
        if result:
            self.result = True
            self.queue.clear()
            return
        identifier, depth = self.current
        if depth < self.node["max_depth"]:
            views = yield from self.access.neighbours_steps(identifier, controls)
            for view in views:
                target = view.target.id
                if target not in self.seen:
                    self.seen.add(target)
                    self.queue.append((target, depth+1))
