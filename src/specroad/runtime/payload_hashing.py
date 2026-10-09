"""Operational outcomes for bounded hashing; no retry or storage authority."""
import errno

from .controlled import _fingerprint_file, _invocation
from ..storage.byte_binding import validate_block_size


_IO_BLOCKERS = {
    errno.EACCES: ('access_denied', 'restore_read_and_traverse_permission'),
    errno.EPERM: ('access_denied', 'restore_read_and_traverse_permission'),
    errno.ENOENT: ('source_missing', 'restore_the_bound_input_then_revalidate'),
    errno.EMFILE: ('descriptor_unavailable', 'make_a_file_descriptor_available'),
    errno.ENFILE: ('descriptor_unavailable', 'make_a_file_descriptor_available'),
    errno.ENOMEM: ('memory_unavailable', 'make_memory_for_the_failed_step_available'),
    errno.ENOSPC: ('storage_unavailable', 'restore_storage_availability'),
    errno.EIO: ('io_failure', 'restore_reliable_source_io'),
    errno.ENOSYS: ('safe_io_unavailable', 'provide_supported_guarded_file_io'),
}
for _name, _reason, _action in (
    ('EDQUOT', 'storage_unavailable', 'restore_storage_availability'),
    ('ENOTSUP', 'safe_io_unavailable', 'provide_supported_guarded_file_io'),
    ('EOPNOTSUPP', 'safe_io_unavailable', 'provide_supported_guarded_file_io'),
):
    if hasattr(errno, _name):
        _IO_BLOCKERS[getattr(errno, _name)] = (_reason, _action)


def fingerprint_file_outcome(boundary, path, call, *, block_size=65536):
    """Return a complete byte fingerprint or an observed, bounded blocker.

    The lower-level fingerprint_file API keeps its native exception contract.
    Safety violations, invalid inputs and unexpected programming failures still
    propagate. No incomplete digest is returned, persisted or automatically
    retried. The caller finishes its active consumption window as usual.
    """
    _invocation(call)
    validate_block_size(block_size)
    attempt = {'stage': 'guarded_open', 'buffer_attempts': [], 'buffer_bytes': None}
    failure = None
    native_errno = None
    try:
        value = _fingerprint_file(boundary, path, call, block_size=block_size, attempt=attempt)
    except MemoryError:
        failure = ('memory_unavailable', 'make_memory_for_the_failed_step_available')
    except OSError as error:
        failure = _IO_BLOCKERS.get(error.errno)
        if failure is None:
            raise
        native_errno = error.errno
    alternatives = {'strategy': 'bounded_streaming', 'requested_block_bytes': block_size,
                    'buffer_attempts_bytes': attempt['buffer_attempts'],
                    'reserved_buffer_bytes': attempt['buffer_bytes']}
    if failure is None:
        return {'format_version': 'payload-hash-outcome-v1', 'state': 'completed', 'exit_code': 0,
                'fingerprint': {'size': value.size, 'sha256': value.sha256},
                'blocker': None, 'transfer': alternatives}
    minimum = (1 if attempt['stage'] == 'buffer_allocation'
               and attempt['buffer_attempts'] and attempt['buffer_attempts'][-1] == 1 else None)
    blocker = {'blocked_reason': failure[0], 'failed_stage': attempt['stage'],
               'native_errno': native_errno, 'required_action': failure[1],
               'minimum_failed_buffer_bytes': minimum,
               'project_writes_performed': False, 'checkpoint': None,
               'retry_requires_input_revalidation': True, 'automatic_retry_performed': False}
    return {'format_version': 'payload-hash-outcome-v1', 'state': 'blocked', 'exit_code': 5,
            'fingerprint': None, 'blocker': blocker, 'transfer': alternatives}
