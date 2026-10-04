"""Native lock, working directory and predecessor bindings for recovery writes."""
import os

from ..security import paths as guards
from ._journal_io import _read
from .locking import HeldProjectLock
from .recovery_values import RecoveryError


def _check_recovery_lock(held, journal, command):
    if type(held) is not HeldProjectLock:
        raise RecoveryError('native_recovery_lock_required', exit_code=7)
    held.check()
    lock, data = held.record.data, journal.data
    if (lock['kind'] != 'recovery' or lock['command'] != command
            or lock['transaction_id'] != data['transaction_id']
            or lock['project_id'] != data['project_id']
            or lock['request_id'] != data['request_id']):
        raise RecoveryError('recovery_lock_binding_mismatch', exit_code=6)


def check_run_lock(held, journal):
    _check_recovery_lock(held, journal, 'recover run')


def check_discard_lock(held, journal):
    _check_recovery_lock(held, journal, 'recover discard')


def check_directory_binding(directory, identity, *, reason='recovery_work_changed', path=None):
    """Keep a reopened directory bound, with the caller's existing conflict path."""
    if directory is None or guards._identity(os.fstat(directory)) != identity:
        raise RecoveryError(reason, path=path, exit_code=6)


def check_journal_binding(directory, journal, directory_identity):
    """Check the work directory before reading its exact journal predecessor."""
    check_directory_binding(directory, directory_identity)
    if _read(directory, 'journal.json') != journal.source_bytes:
        raise RecoveryError('recovery_journal_changed', exit_code=6)
