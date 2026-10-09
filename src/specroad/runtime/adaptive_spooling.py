"""Measured live spool work; no durable checkpoint, command exit or retry.

Only the existing guarded diagnostic/prepared-path tasks are accepted. Their
sources, scratch roots and lifetimes stay explicitly owned by the caller.
"""

from ..diagnostics.spooling import DiagnosticSort
from ..graph.path_output import PathSort
from .controlled import _invocation
from .control_points import PhaseBoundary
from ._spool_work_policy import _IO_BLOCKERS, batch_target, blocked_outcome


def advance_spool_sort(task, call, *, max_units=256):
    """Make actual progress before yielding at an observed soft work target.

    One unit uses the existing live generator, including during an open merge.
    Clock observations never interrupt native I/O or an indivisible record.
    A memory event chooses one-record batches; other soft events cap future
    encoded batching at 64 KiB. Already buffered inputs remain owned until their
    existing flush completes. Original failures propagate without retry.
    """
    return _advance_sort(task, call, max_units=max_units, minimum=False, attempt={})


def _advance_sort(task, call, *, max_units, minimum, attempt):
    _invocation(call)
    if type(task) not in (DiagnosticSort, PathSort):
        raise TypeError("An owned spool sort is required")
    if type(max_units) is not int or max_units < 1:
        raise ValueError("A positive work window is required")
    previous = task.state
    before = task.batch_bytes
    attempt.update(previous=previous, batch_bytes_before=before, unit_attempted=False)
    exceeded = False
    for _ in range(max_units):
        attempt['stage'] = 'control_start'
        observed = call.control(PhaseBoundary("spool_unit", "start"))
        exceeded = exceeded or observed["soft_budget_exceeded"]
        attempt['stage'] = 'adaptation'
        if minimum or exceeded:
            task.reduce_batch_bytes(batch_target(minimum, "memory" in call._events))
        attempt['stage'] = 'spool_advance'
        attempt['unit_attempted'] = not previous['complete']
        current = task.advance(1)
        attempt['stage'] = 'control_end'
        observed = call.control(PhaseBoundary("spool_unit", "end"))
        exceeded = exceeded or observed["soft_budget_exceeded"]
        if exceeded and not current["complete"]:
            task.reduce_batch_bytes(batch_target(False, "memory" in call._events))
        if current["complete"] or exceeded:
            break
    completed = current["units_completed"] - previous["units_completed"]
    attempt['stage'] = 'window_projection'
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


def advance_spool_sort_outcome(task, call, *, max_units=256):
    """Use minimum future batches and report only observed advance failures.

    This conservative entrypoint selects one-record future batches before work;
    an existing buffer or open merge keeps its current contents and cursor.
    It never retries or reopens a failed task. Files survive, but in-memory
    buffers and a failed generator are not advertised as resumable work.
    Validation, safety, observer and unexpected failures retain their exception
    contract. Persistent recovery of the sort is a separate work-v1 concern.
    """
    attempt = {}
    try:
        window = _advance_sort(task, call, max_units=max_units, minimum=True, attempt=attempt)
    except (MemoryError, OSError) as error:
        if attempt.get('stage') != 'spool_advance' or not attempt.get('unit_attempted'):
            raise
        native_errno = error.errno if isinstance(error, OSError) else None
        failure = (('memory_unavailable', 'make_memory_for_the_failed_step_available')
                   if isinstance(error, MemoryError) else _IO_BLOCKERS.get(native_errno))
        if failure is None:
            raise
        current = task.state
        return blocked_outcome(failure, native_errno, attempt, current, task.batch_bytes, max_units)
    return {'format_version': 'spool-work-outcome-v1', 'state': window['state'],
            'exit_code': 0 if window['state'] == 'completed' else None,
            'window': window, 'blocker': None}
