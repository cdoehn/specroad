"""One native lock binding check for explicit transaction recovery actions."""
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
