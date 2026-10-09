"""Measured live spool work; no durable checkpoint, command exit or retry.

Only the existing guarded diagnostic/prepared-path tasks are accepted. Their
sources, scratch roots and lifetimes stay explicitly owned by the caller.
"""

from ..diagnostics.spooling import DiagnosticSort
from ..graph.path_output import PathSort
from .controlled import _invocation
from .control_points import PhaseBoundary


def advance_spool_sort(task, call, *, max_units=256):
    """Make actual progress before yielding at an observed soft work target.

    One unit uses the existing live generator, including during an open merge.
    Clock observations never interrupt native I/O or an indivisible record.
    A memory event chooses one-record batches; other soft events cap future
    encoded batching at 64 KiB. Already buffered inputs remain owned until their
    existing flush completes. Original failures propagate without retry.
    """
    _invocation(call)
    if type(task) not in (DiagnosticSort, PathSort):
        raise TypeError("An owned spool sort is required")
    if type(max_units) is not int or max_units < 1:
        raise ValueError("A positive work window is required")
    previous = task.state
    before = task.batch_bytes
    exceeded = False
    for _ in range(max_units):
        observed = call.control(PhaseBoundary("spool_unit", "start"))
        exceeded = exceeded or observed["soft_budget_exceeded"]
        if exceeded:
            task.reduce_batch_bytes(1 if "memory" in call._events else 65536)
        current = task.advance(1)
        observed = call.control(PhaseBoundary("spool_unit", "end"))
        exceeded = exceeded or observed["soft_budget_exceeded"]
        if exceeded and not current["complete"]:
            task.reduce_batch_bytes(1 if "memory" in call._events else 65536)
        if current["complete"] or exceeded:
            break
    completed = current["units_completed"] - previous["units_completed"]
    return {
        "format_version": "spool-work-window-v1",
        "state": "completed" if current["complete"] else "active",
        "units_completed": completed,
        "progress_made": completed > 0,
        "cursor": current,
        "soft_budget_exceeded": exceeded,
        "adaptation": {"strategy": "external_runs_and_pairwise_merge",
                       "requested_window_units": max_units,
                       "batch_bytes_before": before, "batch_bytes_after": task.batch_bytes,
                       "smallest_unit_attempted": not previous["complete"],
                       "automatic_retry_performed": False},
        "continuation_scope": "same_live_task_in_current_process",
        "durable_checkpoint": False,
        "checkpoint": None,
        "next_action": "read_complete_spool" if current["complete"] else "advance_same_live_sort",
    }
