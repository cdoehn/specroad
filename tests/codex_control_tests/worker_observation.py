"""Bounded observation of one owned worker; no restart or success from saved state."""
import json
import os
import time

from specroad_control.errors import ControlError
from specroad_control.ipc import request
from specroad_control.local import json_read


class WorkerObservationFailure(AssertionError):
    def __init__(self, details):
        self.details = details
        super().__init__(json.dumps(details, sort_keys=True))


def state_summary(state):
    if not isinstance(state, dict):
        return None
    keys = ('phase', 'desired', 'active_job', 'runtime_error', 'stop_reason')
    result = {key: state.get(key) for key in keys}
    automation = state.get('automation') or {}
    if not isinstance(automation, dict):
        automation = {}
    result['automation'] = {key: automation.get(key) for key in
        ('stage', 'error', 'retry_attempt', 'retry_at', 'retry_blocked_reason')}
    return result


def failure(paths, child, log, stage, reason, last):
    details = {'reason': reason, 'expected_stage': stage, 'exit_code': child.poll(),
               'last_live_state': state_summary(last), 'persisted_state': None,
               'state_error': None, 'log_error': None, 'log_tail': ''}
    try:
        details['persisted_state'] = state_summary(json_read(paths.state_file))
    except (ControlError, OSError) as error:
        details['state_error'] = error.code if isinstance(error, ControlError) else type(error).__name__
    try:
        size = os.fstat(log.fileno()).st_size
        # pread preserves the shared file offset of the still-running writer.
        details['log_tail'] = os.pread(log.fileno(), 16384, max(0, size - 16384)).decode(errors='replace')
    except (OSError, ValueError) as error:
        details['log_error'] = type(error).__name__
    raise WorkerObservationFailure(details)


def wait_stage(paths, child, log, stage, seconds=10, *, status=request,
               clock=time.monotonic, sleep=time.sleep):
    deadline = clock() + seconds
    last = None
    while clock() < deadline:
        if child.poll() is not None:
            failure(paths, child, log, stage, 'worker_exited', last)
        try:
            state = status(paths, 'status')['state']
        except ControlError as error:
            if error.code != 'not_running':
                raise
            if child.poll() is not None:
                failure(paths, child, log, stage, 'worker_exited', last)
        else:
            last = state
            if child.poll() is not None:
                failure(paths, child, log, stage, 'worker_exited', last)
            if (state.get('automation') or {}).get('stage') == stage:
                return state
        sleep(.03)
    failure(paths, child, log, stage,
            'worker_exited' if child.poll() is not None else 'deadline_expired', last)
