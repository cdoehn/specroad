"""Closed static SRX graph selectors; no dynamic expressions or implicit limits."""

from ..graph.relation_types import CORE_RELATION_TYPES
from ..model.artifact_types import artifact_types
from ._json_values import json_type
from .errors import SrxError

GRAPH_OPERATORS = ("relation_count", "incoming_count", "has_relation", "reachable")
GRAPH_REQUIRED = {
    "relation_count": ("op", "direction", "types"),
    "incoming_count": ("op", "types"),
    "has_relation": ("op", "direction", "types"),
    "reachable": ("op", "direction", "types", "where", "max_depth"),
}
GRAPH_OPTIONAL = {"has_relation": ("target_type", "target_id")}


def validate_graph_node(node, *, rule_id, at):
    op = node["op"]
    required = set(GRAPH_REQUIRED[op])
    allowed = required | set(GRAPH_OPTIONAL.get(op, ()))
    if not required <= node.keys() or not node.keys() <= allowed:
        raise SrxError("invalid_fields", rule_id=rule_id, pointer=at,
                       expected="closed graph expression", actual="object")
    def bad(reason, field, expected):
        raise SrxError(reason, rule_id=rule_id, pointer=at+"/"+field,
                       expected=expected, actual=json_type(node[field]))
    if op != "incoming_count":
        if type(node["direction"]) is not str or node["direction"] not in ("outgoing", "incoming", "both"):
            bad("invalid_graph_direction", "direction", "outgoing, incoming or both")
    selected = node["types"]
    if not (type(selected) is str and selected == "*"):
        if type(selected) is not list:
            bad("graph_types_required", "types", "explicit type list or *")
        seen = set()
        for kind in selected:
            if type(kind) is not str or kind not in (*CORE_RELATION_TYPES, "superseded_by"):
                bad("unknown_graph_relation_type", "types", "known relation types")
            if kind in seen:
                bad("duplicate_graph_relation_type", "types", "unique type selectors")
            seen.add(kind)
    if op == "reachable" and (type(node["max_depth"]) is not int or node["max_depth"] < 0):
        bad("invalid_graph_depth", "max_depth", "explicit nonnegative integer")
    if "target_type" in node:
        if type(node["target_type"]) is not str or node["target_type"] not in {x.artifact_type for x in artifact_types()}:
            bad("invalid_graph_target_type", "target_type", "known artifact type")
    if "target_id" in node:
        if type(node["target_id"]) is not str or not node["target_id"] or node["target_id"].strip() != node["target_id"]:
            bad("invalid_graph_target_id", "target_id", "nonempty exact artifact ID")
