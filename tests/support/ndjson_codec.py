"""Explicit native transport fixtures; no real model or approval is claimed."""
from copy import deepcopy

from specroad.changes import prepare_change_plan
from .change_plans import document, operation, result
from .domain import domain_value


def envelope(value, kind="artifact"):
    return {"format_version": "1.0.0", "object_kind": kind, "object": deepcopy(value)}


def plan_value():
    # One native plan with ordered patches and operations, never executed.
    first = operation("update")
    first["patch"] = [{"op": "test", "path": "/statement", "value": "Original"},
                      {"op": "replace", "path": "/statement", "value": "Intermediate"}]
    second = operation("update")
    second["patch"] = [{"op": "replace", "path": "/statement", "value": "Final"}]
    return prepare_change_plan(document([first, second], [result(domain_value(statement="Final", revision=2))])).data
