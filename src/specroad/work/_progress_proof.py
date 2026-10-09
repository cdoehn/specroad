"""Proof of confirmed progress and inspection of retained storage.

These checks do not choose work, retry a failed attempt or authorize execution.
"""

from ..model.errors import ModelError
from ..security import SafetyViolation
from ._data_contract import WorkManifestError
from .checkpoints import CheckpointStorageError
from .manifest import read_work_successor
from .resume import _compatible_read, _require


def confirmed_window_data(store, step, start, end):
    """Check the actual successor/reuse and preserve its measured projection."""
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
        'consumption_persisted': False, 'global_finalization_required': value['state'] != 'completed',
    }
    return window


def _retained_checkpoint(store):
    """Read current actual storage once; never assume an error rolled it back."""
    try:
        current = store.read()
        if current is None:
            return {'status': 'unpublished', 'checkpoint': None, 'error': None}
        value = current.as_dict()
        return {'status': 'verified_storage_chain', 'checkpoint': {
            'work_id': value['work_id'], 'checkpoint_generation': value['checkpoint_generation'],
            'checkpoint_sha256': value['checkpoint_sha256'],
            'completed_unit_ids': [row['unit_id'] for row in current.entries('completed')],
            'work_state': value['state']}, 'error': None}
    except (OSError, MemoryError, CheckpointStorageError, WorkManifestError,
            SafetyViolation, ModelError) as error:
        return {'status': 'unavailable', 'checkpoint': None,
                'error': {'type': type(error).__name__,
                          'reason': getattr(error, 'reason', None),
                          'native_errno': error.errno if isinstance(error, OSError) else None}}
