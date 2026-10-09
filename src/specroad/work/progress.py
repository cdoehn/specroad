"""Measured minimum progress for the existing closed read-only handler plan.

The complete handler is the supported indivisible unit. A soft target never
prevents its attempt or interrupts checkpoint publication. Multi-unit planning,
global work finalization and persistent consumption remain separate contracts.
"""

from dataclasses import dataclass
import errno

from ..model.canonical import canonical_json_bytes
from ..runtime.controlled import _invocation
from ..runtime.control_points import PhaseBoundary
from ._data_contract import _parse
from .checkpoints import CheckpointStore
from ._progress_proof import confirmed_window_data, _retained_checkpoint
from .resume import resume_read_only_work, _require


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
    return _advance_read_only_work(store, call, cwd=cwd, attempt={})


def _advance_read_only_work(store, call, *, cwd, attempt):
    _invocation(call)
    _require(type(store) is CheckpointStore, 'trusted_work_store_required')
    attempt['stage'] = 'control_start'
    start = call.control(PhaseBoundary('work_unit', 'start'))
    # The existing closed plan's only unit is the full safe bootstrap handler.
    # Measuring a soft overshoot must not produce a generation with zero work.
    attempt['stage'] = 'resume'
    step = resume_read_only_work(store, cwd=cwd)
    attempt['stage'] = 'control_end'
    end = call.control(PhaseBoundary('work_unit', 'end'))
    attempt['stage'] = 'progress_confirmation'
    window = confirmed_window_data(store, step, start, end)
    result = object.__new__(ReadOnlyWorkWindow)
    object.__setattr__(result, 'step', step)
    object.__setattr__(result, '_window_bytes', canonical_json_bytes(window))
    return result


_IO_BLOCKERS = {
    errno.ENOSPC: ('storage_unavailable', 'provide_space_for_external_work_storage'),
    errno.ENOMEM: ('memory_unavailable', 'make_memory_for_the_required_resume_stage_available'),
    errno.EMFILE: ('descriptor_unavailable', 'make_a_file_descriptor_available'),
    errno.ENFILE: ('descriptor_unavailable', 'make_a_file_descriptor_available'),
    errno.EACCES: ('access_denied', 'restore_permissions_for_bound_work_and_protected_roots'),
    errno.EPERM: ('access_denied', 'restore_permissions_for_bound_work_and_protected_roots'),
    errno.EROFS: ('read_only_storage', 'provide_writable_external_work_storage'),
    errno.ENOENT: ('bound_path_missing', 'restore_required_bound_bytes_and_paths_then_revalidate'),
    errno.EIO: ('io_failure', 'restore_reliable_bound_work_io'),
}
if hasattr(errno, 'EDQUOT'):
    _IO_BLOCKERS[errno.EDQUOT] = ('storage_unavailable', 'provide_quota_for_external_work_storage')


def advance_read_only_work_outcome(store, call, *, cwd=None):
    """Report an observed resume resource failure separately from work progress.

    Validation, compatibility, safety and unexpected errors retain their native
    exception contract. Only failures from the resume stage are classified;
    measurement/projection failures cannot masquerade as failed minimum work.
    Blockers are returned data, not newly published WorkManifest generations.
    """
    attempt = {}
    try:
        window = _advance_read_only_work(store, call, cwd=cwd, attempt=attempt)
    except (MemoryError, OSError) as error:
        if attempt.get('stage') != 'resume':
            raise
        native_errno = error.errno if isinstance(error, OSError) else None
        failure = (('memory_unavailable', 'make_memory_for_the_required_resume_stage_available')
                   if isinstance(error, MemoryError) else _IO_BLOCKERS.get(native_errno))
        if failure is None:
            raise
        blocker = {'blocked_reason': failure[0], 'required_action': failure[1],
            'native_errno': native_errno, 'failed_stage': 'resume',
            'failure_basis': 'observed_exception_from_resume',
            'minimum_resources_known': False, 'smallest_unit_attempted': None,
            'attempt_detail': 'no_complete_handler_window_confirmed',
            'retained': _retained_checkpoint(store),
            'retained_verification_scope': 'stored_chain_only_not_execution_authority',
            'automatic_retry_performed': False, 'blocker_persisted': False,
            'next_action': 'remedy_observed_resource_then_revalidate_work',
            'project_writes_performed': False, 'critical_data_deleted': False}
        return {'format_version': 'read-only-work-outcome-v1', 'state': 'blocked',
                'exit_code': 5, 'window': None, 'blocker': blocker,
                'global_finalization_required': True}
    projection = window.as_dict()
    return {'format_version': 'read-only-work-outcome-v1', 'state': 'unit_result_available',
            'exit_code': window.step.command_exit_code, 'window': projection,
            'blocker': None, 'global_finalization_required': projection['global_finalization_required']}
