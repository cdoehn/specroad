"""Synchronous ownership of one explicitly trusted direct child per call.

This host API is not a command resolver or permission to execute Work/project
data. The caller supplies the trusted executable, arguments, cwd and complete
environment. No shell, pool, daemon, retry, interactive stdin or job timeout is
introduced. Initial I/O is whole-byte; streaming adapters are separate work.
"""

import os
import subprocess


class ChildContractError(ValueError):
    def __init__(self, reason, *, exit_code=2):
        super().__init__(reason)
        self.reason, self.exit_code = reason, exit_code

    def as_dict(self):
        return {'reason': self.reason, 'exit_code': self.exit_code}


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
    A handled exception terminates and reaps our direct child before propagating.
    Cleanup owns pipes/process lifetime, never Work or recovery files. The child
    must be trusted not to daemonize; this is not a sandbox for arbitrary code.
    Fatal host termination cannot execute Python cleanup.
    """
    environment = _contract(arguments, cwd, environment, input_bytes)
    process = subprocess.Popen(arguments, cwd=cwd, env=environment,
        stdin=subprocess.DEVNULL if input_bytes is None else subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
        shell=False, close_fds=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(input_bytes)
        return subprocess.CompletedProcess(arguments, process.returncode, stdout, stderr)
    finally:
        try:
            if process.poll() is None:
                process.kill()
            process.wait()
        finally:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
