"""Synchronous ownership of one explicitly trusted direct child per call.

This host API is not a command resolver or permission to execute Work/project
data. The caller supplies the trusted executable, arguments, cwd and complete
environment. No shell, pool, daemon, retry, interactive stdin or job timeout is
introduced. Initial I/O is whole-byte; streaming adapters are separate work.
"""

import os
import subprocess
import sys

from ._child_cleanup import finish_child as _finish_owned_child


class ChildContractError(ValueError):
    def __init__(self, reason, *, exit_code=2):
        super().__init__(reason)
        self.reason, self.exit_code = reason, exit_code

    def as_dict(self):
        return {'reason': self.reason, 'exit_code': self.exit_code}


class ChildCleanupError(RuntimeError):
    """A failed cleanup with observed state, never permission to kill a PID."""

    def __init__(self, process, failures, *, interrupted):
        super().__init__('child_cleanup_incomplete')
        self.reason, self.exit_code = 'child_cleanup_incomplete', 5
        self.pid, self.returncode = process.pid, process.returncode
        self.child_reaped = process.returncode is not None
        self.open_pipes = tuple(name for name in ('stdin', 'stdout', 'stderr')
            if getattr(process, name) is not None and not getattr(process, name).closed)
        self.failures = tuple((operation, type(error).__name__) for operation, error in failures)
        self.interrupted = interrupted

    def as_dict(self):
        return {'reason': self.reason, 'exit_code': self.exit_code, 'pid': self.pid,
                'returncode': self.returncode, 'child_reaped': self.child_reaped,
                'open_pipes': list(self.open_pipes), 'interrupted': self.interrupted,
                'failures': [{'operation': name, 'error_type': kind} for name, kind in self.failures]}


def _finish(process, primary):
    return _finish_owned_child(process, primary, ChildCleanupError)

def _contract(arguments, cwd, environment, input_bytes):
    if (type(arguments) is not tuple or not arguments
            or any(type(item) is not str or '\0' in item for item in arguments)
            or not os.path.isabs(arguments[0])
            or type(cwd) is not str or not os.path.isabs(cwd) or '\0' in cwd
            or type(environment) is not dict
            or any(type(key) is not str or not key or '=' in key or '\0' in key
                   or type(value) is not str or '\0' in value
                   for key, value in environment.items())
            or (input_bytes is not None and type(input_bytes) is not bytes)):
        raise ChildContractError('invalid_child_contract')
    if os.name != 'posix':
        raise ChildContractError('unsupported_child_platform', exit_code=5)
    return dict(environment)


def run_child(arguments, *, cwd, environment, input_bytes=None):
    """Return the actual status and binary streams only after child cleanup.

    Nonzero/signal exit status remains data, never a fabricated command success.
    A handled exception attempts termination and collection before propagating;
    failed cleanup raises ChildCleanupError with the actual observed state.
    Cleanup owns pipes/process lifetime, never Work or recovery files. The child
    must be trusted not to daemonize; this is not a sandbox for arbitrary code.
    Fatal host termination cannot execute Python cleanup.
    """
    environment = _contract(arguments, cwd, environment, input_bytes)
    process = None
    try:
        process = subprocess.Popen(arguments, cwd=cwd, env=environment,
            stdin=subprocess.DEVNULL if input_bytes is None else subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
            shell=False, close_fds=True, start_new_session=True)
        stdout, stderr = process.communicate(input_bytes)
        return subprocess.CompletedProcess(arguments, process.returncode, stdout, stderr)
    finally:
        if process is not None:
            _finish(process, sys.exc_info()[1])
