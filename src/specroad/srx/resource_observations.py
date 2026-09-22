"""Immutable observations, distinct from rule values, policies and scheduling."""
from dataclasses import dataclass
from .resource_policy import VERSION, ResourcePolicy


@dataclass(frozen=True)
class StructureObservation:
    ast_nodes: int
    ast_depth: int

    def __post_init__(self):
        if (type(self.ast_nodes) is not int or type(self.ast_depth) is not int
                or not 1 <= self.ast_depth <= self.ast_nodes):
            raise ValueError("Invalid AST observation")

    @property
    def data(self):
        return {"ast_nodes": self.ast_nodes, "ast_depth": self.ast_depth}


@dataclass(frozen=True)
class SoftTargetEvent:
    """First measured crossing, not a rule error or a persistent checkpoint."""
    metric: str
    target: int
    observed: int
    pointer: str

    def __post_init__(self):
        if (type(self.metric) is not str or self.metric not in ("evaluation_steps", "iterations", "graph_steps")
                or type(self.target) is not int or type(self.observed) is not int
                or not 1 <= self.target < self.observed or type(self.pointer) is not str
                or not self.pointer.startswith("/expression")):
            raise ValueError("Invalid soft work event")

    @property
    def data(self):
        return {"kind": "soft_budget_exceeded", "metric": self.metric, "target": self.target,
                "observed": self.observed, "expression_pointer": self.pointer,
                "continuation_reason": "continue_without_truncating_or_loosening_limits"}


@dataclass(frozen=True)
class ResourceUsage:
    structure: StructureObservation
    policy: ResourcePolicy
    evaluation_steps: int
    iterations: int
    graph_steps: int
    evaluation_completed: bool
    events: tuple = ()

    def __post_init__(self):
        if (type(self.structure) is not StructureObservation or type(self.policy) is not ResourcePolicy
                or type(self.evaluation_completed) is not bool or type(self.events) is not tuple):
            raise ValueError("Invalid resource observation")
        counts = {"evaluation_steps": self.evaluation_steps, "iterations": self.iterations,
                  "graph_steps": self.graph_steps}
        if any(type(value) is not int or value < 0 for value in counts.values()):
            raise ValueError("Invalid resource counters")
        seen = set()
        targets = self.policy.work.data
        for event in self.events:
            if (type(event) is not SoftTargetEvent or event.metric in seen
                    or event.target != targets[event.metric] or event.observed > counts[event.metric]):
                raise ValueError("Inconsistent soft work event")
            seen.add(event.metric)
        if seen != {name for name, value in counts.items() if value > targets[name]}:
            raise ValueError("Missing or extra soft work event")

    @property
    def data(self):
        counts = {"evaluation_steps": self.evaluation_steps,
                  "iterations": self.iterations, "graph_steps": self.graph_steps}
        exceeded = [name for name, count in counts.items() if count > self.policy.work.data[name]]
        return {"version": VERSION, "structure": self.structure.data, "policy": self.policy.data,
                "work_counts": counts, "soft_budget_exceeded": bool(exceeded),
                "exceeded_targets": exceeded, "events": [event.data for event in self.events],
                "evaluation_completed": self.evaluation_completed,
                "continuation": "in_process" if exceeded else "not_needed",
                "checkpoint": None, "resume_available": False,
                "observation_scope": "expression_dispatch_quantifier_items_and_graph_reads"}


