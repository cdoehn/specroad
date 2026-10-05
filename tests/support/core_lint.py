"""Owned sources for actual lint rules; stored approval is not review evidence."""
from specroad.graph.relations import SourceRelations
from specroad.model.paths import artifact_path
from .artifacts import artifact_bytes
from .domain import approved_value, domain_value
from .model_validation import edge
from .records import record_value


def requirement_graph():
    requirement = approved_value("requirement", language="en")
    goal = domain_value("goal")
    verification = record_value("verification", subjects=[requirement["id"]])
    requirement["relations"] = [edge(goal, "addresses", 1),
                                edge(verification, "verified_by", 2)]
    return requirement, goal, verification


def sources(values):
    return tuple(SourceRelations(artifact_bytes(v),
        path=artifact_path(v["artifact_type"], v["id"], "SR")) for v in values)
