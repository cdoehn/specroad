"""Explicit AST safety policy and non-failing work targets.

The built-in srx-resource-v1 library profile is explicit in every observation.
It is not an OS quota, a timeout, or a verified checkpoint. Work targets never
change an operator result or loosen a structural boundary.
"""
from dataclasses import dataclass
from .errors import SrxError

VERSION = "srx-resource-v1"


class SrxResourcePolicyError(SrxError):
    def __init__(self, *, rule_id=None, pointer="/project/resource_limits"):
        super().__init__("invalid_resource_policy", rule_id=rule_id, pointer=pointer,
                         expected="positive integer SRX limits and work targets",
                         actual="invalid_policy", subject="context")
        self.exit_code = 2

    def diagnostic(self):
        return {**super().diagnostic(), "exit_code": self.exit_code}


class SrxStructureError(SrxError):
    def __init__(self, metric, limit, observed, *, rule_id, pointer):
        super().__init__(metric + "_exceeded", rule_id=rule_id, pointer=pointer,
                         expected="AST within declared structural limits", actual="structure_over_limit")
        self.code = "SRV111"
        self.exit_code = 3
        self.metric, self.limit, self.observed = metric, limit, observed

    def diagnostic(self):
        return {**super().diagnostic(), "exit_code": self.exit_code,
                "limit_class": "hard_safety_or_format", "metric": self.metric,
                "limit": self.limit, "observed": self.observed,
                "recommendation": "Reduce the expression structure or explicitly review its safety policy; never relax it automatically."}


def _positive(value, pointer, rule_id=None):
    if type(value) is not int or value < 1:
        raise SrxResourcePolicyError(rule_id=rule_id, pointer=pointer)
    return value


@dataclass(frozen=True)
class StructureLimits:
    """Operator occurrences, root depth one; literal JSON values are not ASTs.

    These versioned library defaults preserve the supported deep-expression
    corpus. They are not claimed as normative release-wide profile defaults.
    Callers may explicitly select another positive structural policy.
    """
    ast_nodes: int = 10000
    ast_depth: int = 2048

    def __post_init__(self):
        _positive(self.ast_nodes, "/structure/ast_nodes")
        _positive(self.ast_depth, "/structure/ast_depth")

    @property
    def data(self):
        return {"ast_nodes": self.ast_nodes, "ast_depth": self.ast_depth}


@dataclass(frozen=True)
class WorkTargets:
    evaluation_steps: int = 1000000
    iterations: int = 1000000
    graph_steps: int = 2000000

    def __post_init__(self):
        for name in ("evaluation_steps", "iterations", "graph_steps"):
            _positive(getattr(self, name), "/work_targets/" + name)

    @property
    def data(self):
        return {"evaluation_steps": self.evaluation_steps,
                "iterations": self.iterations, "graph_steps": self.graph_steps}


@dataclass(frozen=True)
class ResourcePolicy:
    structure: StructureLimits = StructureLimits()
    work: WorkTargets = WorkTargets()

    def __post_init__(self):
        if type(self.structure) is not StructureLimits or type(self.work) is not WorkTargets:
            raise SrxResourcePolicyError()

    @property
    def data(self):
        return {"version": VERSION, "structure": self.structure.data,
                "work_targets": self.work.data}

    @classmethod
    def from_project(cls, project, *, rule_id, resource_options=None):
        if type(project) is not dict:
            raise SrxResourcePolicyError(rule_id=rule_id, pointer="/project")
        raw = project.get("resource_limits", {})
        if type(raw) is not dict or any(type(key) is not str for key in raw):
            raise SrxResourcePolicyError(rule_id=rule_id)
        defaults = {"srx_nodes": 10000, "srx_depth": 2048, "srx_operations": 1000000,
                    "srx_iterations": 1000000, "srx_graph_steps": 2000000}
        if resource_options is not None:
            from ..runtime.budget_policy import ResourcePolicyError, resolve_resource_policy
            try:
                runtime = resolve_resource_policy(resource_options)
            except ResourcePolicyError as error:
                raise SrxResourcePolicyError(rule_id=rule_id, pointer='/resource_options') from error
            defaults['srx_graph_steps'] = runtime['effective_budgets']['graph']['value']
        unknown = sorted(key for key in raw if key.startswith("srx_") and key not in defaults)
        if unknown:
            raise SrxResourcePolicyError(rule_id=rule_id, pointer="/project/resource_limits/" + unknown[0].replace("~", "~0").replace("/", "~1"))
        values = {name: _positive(raw.get(name, default), "/project/resource_limits/" + name, rule_id)
                  for name, default in defaults.items()}
        return cls(StructureLimits(values["srx_nodes"], values["srx_depth"]),
                   WorkTargets(values["srx_operations"], values["srx_iterations"], values["srx_graph_steps"]))


