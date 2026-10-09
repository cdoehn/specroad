"""Measured minimum progress for the existing closed read-only handler plan.

The complete handler is the supported indivisible unit. A soft target never
prevents its attempt or interrupts checkpoint publication. Multi-unit planning,
global work finalization and persistent consumption remain separate contracts.
"""

from dataclasses import dataclass

from ..model.canonical import canonical_json_bytes
from ..runtime.controlled import _invocation
from ..runtime.control_points import PhaseBoundary
from ._data_contract import _parse
from .checkpoints import CheckpointStore
from .manifest import read_work_successor
from .resume import resume_read_only_work, _require, _compatible_read


@dataclass(frozen=True, init=False)
class ReadOnlyWorkWindow:
    """Confirmed handler progress and detached operational window observations."""

    step: object
    _window_bytes: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use advance_read_only_work')

    def as_dict(self):
        return {**_parse(self._window_bytes), 'step': self.step.as_dict()}


def advance_read_only_work(store, call, *, cwd=None):
    """Attempt one safe complete handler even after a soft window is exceeded.

    Callers own the active InvocationConsumption and finish it, also on errors.
    Saved outputs are rechecked and reused without an extra checkpoint. Actual
    work failures propagate with their existing code and storage state; this
    function neither retries nor invents a persisted blocker or Code 8 result.
    """
    _invocation(call)
    _require(type(store) is CheckpointStore, 'trusted_work_store_required')
    start = call.control(PhaseBoundary('work_unit', 'start'))
    # The existing closed plan's only unit is the full safe bootstrap handler.
    # Measuring a soft overshoot must not produce a generation with zero work.
    step = resume_read_only_work(store, cwd=cwd)
    end = call.control(PhaseBoundary('work_unit', 'end'))
    current = step.manifest
    value = current.as_dict()
    completed = current.entries('completed')
    _require(len(completed) == 1 and not current.entries('remaining'),
             'unconfirmed_handler_progress')
    if step.executed:
        previous = store._initial
        _compatible_read(read_work_successor, current.raw, current.objects,
            previous=previous, registry=current._registry,
            expected_tool_build=value['tool_build'])
        _require(not previous.entries('completed'), 'repeated_handler_progress')
    else:
        previous = current
    exceeded = start['soft_budget_exceeded'] or end['soft_budget_exceeded']
    window = {
        'format_version': 'read-only-work-window-v1',
        'minimum_unit': 'complete_read_only_handler',
        'previous_checkpoint_generation': previous.as_dict()['checkpoint_generation'],
        'previous_checkpoint_sha256': previous.as_dict()['checkpoint_sha256'],
        'new_completed_unit_ids': [completed[0]['unit_id']] if step.executed else [],
        'reused_completed_unit_ids': [] if step.executed else [completed[0]['unit_id']],
        'progress_made': step.executed, 'checkpoint_changed': step.executed,
        'smallest_unit_attempted': step.executed,
        'soft_budget_exceeded': exceeded,
        'window_reason': ('reuse_completed_unit' if not step.executed else
                          'minimum_unit_completed_above_soft_target' if exceeded else
                          'complete_single_handler'),
        'observations': {'before': start, 'after': end},
        'consumption_scope': 'caller_owned_in_process_invocation',
        'consumption_persisted': False, 'global_finalization_required': True,
    }
    result = object.__new__(ReadOnlyWorkWindow)
    object.__setattr__(result, 'step', step)
    object.__setattr__(result, '_window_bytes', canonical_json_bytes(window))
    return result
