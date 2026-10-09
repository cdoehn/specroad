"""Pure spool adaptation choices and detached blocker values; no task or I/O."""

import errno


_IO_BLOCKERS = {
    errno.EACCES: ('access_denied', 'restore_guarded_spool_and_source_permissions'),
    errno.EPERM: ('access_denied', 'restore_guarded_spool_and_source_permissions'),
    errno.ENOENT: ('bound_path_missing', 'restore_bound_inputs_and_spool_paths_then_revalidate'),
    errno.EMFILE: ('descriptor_unavailable', 'make_a_file_descriptor_available'),
    errno.ENFILE: ('descriptor_unavailable', 'make_a_file_descriptor_available'),
    errno.ENOMEM: ('memory_unavailable', 'make_memory_for_the_failed_step_available'),
    errno.ENOSPC: ('storage_unavailable', 'make_space_available_without_deleting_recovery_data'),
    errno.EFBIG: ('file_size_limit', 'provide_a_file_size_limit_that_allows_the_required_spool'),
    errno.EROFS: ('read_only_storage', 'provide_writable_external_spool_storage'),
    errno.EIO: ('io_failure', 'restore_reliable_source_and_spool_io'),
    errno.ENOSYS: ('safe_io_unavailable', 'provide_supported_guarded_file_io'),
}
for _name, _reason, _action in (
    ('EDQUOT', 'storage_unavailable', 'make_space_available_without_deleting_recovery_data'),
    ('ENOTSUP', 'safe_io_unavailable', 'provide_supported_guarded_file_io'),
    ('EOPNOTSUPP', 'safe_io_unavailable', 'provide_supported_guarded_file_io'),
):
    if hasattr(errno, _name):
        _IO_BLOCKERS[getattr(errno, _name)] = (_reason, _action)


def batch_target(minimum, memory_event):
    """Choose the existing future encoded batch target from observed signals."""
    return 1 if minimum or memory_event else 65536


def blocked_outcome(failure, native_errno, attempt, current, batch_bytes, max_units):
    previous = attempt['previous']
    blocker = {
        'blocked_reason': failure[0], 'required_action': failure[1],
        'native_errno': native_errno, 'failed_stage': 'spool_advance',
        'failure_basis': 'observed_exception_in_minimum_advance',
        'minimum_resources_known': False,
        'alternatives': {
            'strategy': 'external_runs_and_pairwise_merge',
            'requested_window_units': max_units,
            'batch_bytes_before': attempt['batch_bytes_before'],
            'batch_bytes_after': batch_bytes,
            'buffered_records_before': previous['buffered_records'],
            'pending_input_sequence_before': previous['pending_input_sequence'],
            'smallest_unit_attempted': True, 'automatic_retry_performed': False,
        },
        'retained_progress': {
            'observed_cursor': current,
            'units_completed_in_window': current['units_completed'] - previous['units_completed'],
            'external_spool_files_deleted': False,
            'artifact_validation': 'last_observed_cursor_only',
            'live_task_resumable': False, 'buffered_input_resumable': False,
            'durable_checkpoint': False, 'checkpoint': None,
        },
        'project_writes_performed': False, 'critical_data_deleted': False,
        'next_action': 'after_remedy_revalidate_source_and_start_new_task_in_new_spool',
    }
    return {'format_version': 'spool-work-outcome-v1', 'state': 'blocked',
            'exit_code': 5, 'window': None, 'blocker': blocker}
