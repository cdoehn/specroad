"""Per-call accounting outside scalar/quantifier semantics; no work scheduler.

Future checkpoint adapters can inspect immutable observations without turning
soft work targets into operator errors or changing the ordered AST traversal.
"""
from .errors import SrxError
from .resource_policy import SrxStructureError
from .resource_observations import ResourceUsage, SoftTargetEvent, StructureObservation


class WorkMeter:
    """One local accumulator. No callbacks, clocks, environment or global state."""
    def __init__(self, policy, structure):
        self.policy, self.structure = policy, structure
        self.evaluation_steps = self.iterations = self.graph_steps = 0
        self.events = []
        self.crossed = set()

    def add(self, metric, count=1, *, pointer="/expression"):
        if metric not in ("evaluation_steps", "iterations", "graph_steps") or type(count) is not int or count < 0:
            raise ValueError("Invalid work observation")
        observed = getattr(self, metric) + count
        target = self.policy.work.data[metric]
        if observed > target and metric not in self.crossed:
            self.events.append(SoftTargetEvent(metric, target, observed, pointer))
            self.crossed.add(metric)
        setattr(self, metric, observed)

    def observation(self, completed):
        return ResourceUsage(self.structure, self.policy, self.evaluation_steps,
                             self.iterations, self.graph_steps, completed, tuple(self.events))


class StructureCounter:
    """Track occurrence-based AST size and active ancestry, independently of grammar."""
    def __init__(self, limits, rule_id):
        self.limits, self.rule_id = limits, rule_id
        self.nodes = self.depth = 0
        self.active = set()

    def enter(self, node, at, depth):
        if id(node) in self.active:
            raise SrxError("cyclic_json_value", rule_id=self.rule_id, pointer=at,
                           expected="acyclic AST", actual="object")
        self.nodes += 1
        self.depth = max(self.depth, depth)
        if self.nodes > self.limits.ast_nodes:
            raise SrxStructureError("ast_nodes", self.limits.ast_nodes, self.nodes,
                                    rule_id=self.rule_id, pointer=at)
        if depth > self.limits.ast_depth:
            raise SrxStructureError("ast_depth", self.limits.ast_depth, depth,
                                    rule_id=self.rule_id, pointer=at)

    def hold(self, node):
        self.active.add(id(node))

    def leave(self, owner):
        self.active.remove(owner)

    def observation(self):
        return StructureObservation(self.nodes, self.depth)
