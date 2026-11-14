"""Linux worker supervisor. Own descendants only; cancellation is token-bound.

This executable is the parent of one execnet interpreter. Its private socket
remains independent of pytest, fixtures, worker threads and the SSH data pipe.
An acknowledgement means every owned process has been reaped, not just that
a signal was sent. Failure to prove that fact never authorizes a new attempt.
"""
import ctypes
import json
import os
from pathlib import Path
import re
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
import uuid


def children(pid):
    result = set()
    for task in Path('/proc', str(pid), 'task').glob('*'):
        try:
            result.update(map(int, (task / 'children').read_text().split()))
        except FileNotFoundError:
            pass
    return result


def stamp(pid):
    try:
        value = Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()
        return value[19], value[0]
    except FileNotFoundError:
        return None


def terminate_tree(timeout=10):
    """Freeze the owned tree before killing; pidfds rule out PID reuse kills."""
    deadline = time.monotonic() + timeout
    held = {}
    try:
        while True:
            pending = list(children(os.getpid()))
            seen = set()
            while pending:
                pid = pending.pop()
                if pid in seen:
                    continue
                seen.add(pid)
                before = stamp(pid)
                if before is None:
                    continue
                if pid not in held:
                    try:
                        fd = os.pidfd_open(pid)
                    except ProcessLookupError:
                        continue
                    after = stamp(pid)
                    if after is None or after[0] != before[0]:
                        os.close(fd)
                        raise ValueError('Owned process changed identity')
                    held[pid] = fd
                    try:
                        signal.pidfd_send_signal(fd, signal.SIGSTOP)
                    except ProcessLookupError:
                        pass
                pending.extend(children(pid))
            states = [stamp(pid) for pid in seen]
            if all(s is None or s[1] in ('T', 't', 'Z', 'X') for s in states):
                # Once every parent/thread is frozen, no new descendants can
                # escape discovery. Detached double forks belong to us because
                # this process is the dedicated subreaper for this worker.
                if children(os.getpid()) <= seen:
                    break
            if time.monotonic() >= deadline:
                raise TimeoutError('Owned process tree did not stop')
            time.sleep(0.01)
        for fd in held.values():
            try:
                signal.pidfd_send_signal(fd, signal.SIGKILL)
            except ProcessLookupError:
                pass
        while True:
            try:
                pid, _ = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return time.monotonic_ns()
            if not pid:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Owned process tree did not exit')
                time.sleep(0.01)
    finally:
        for fd in held.values():
            # An incomplete acknowledgement is still a gate failure. Do not
            # strand frozen owned processes on that error path.
            try:
                signal.pidfd_send_signal(fd, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.close(fd)


def request(endpoint, secret, command, **values):
    path = Path(endpoint)
    if (not path.is_absolute() or '..' in path.parts or path.name != 'control.sock'
            or any(p.is_symlink() for p in (path, *path.parents))):
        raise ValueError('Invalid supervisor endpoint')
    info = path.parent.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Supervisor directory is not private')
    if not stat.S_ISSOCK(path.lstat().st_mode) or not re.fullmatch('[0-9a-f]{32}', secret):
        raise ValueError('Invalid supervisor endpoint identity')
    with socket.socket(socket.AF_UNIX) as channel:
        channel.settimeout(15)
        channel.connect(str(path))
        _, uid, _ = struct.unpack('3i', channel.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if uid != os.getuid():
            raise ValueError('Foreign supervisor peer')
        channel.sendall(json.dumps(dict(secret=secret, command=command, **values)).encode() + b'\n')
        value = channel.makefile('rb').readline(65537)
    if len(value) > 65536 or not value.endswith(b'\n'):
        raise ValueError('Invalid supervisor response')
    result = json.loads(value)
    if result.get('error'):
        raise ValueError(result['error'])
    return result


def worker_request(command, **values):
    return request(os.environ['SPECROAD_ATTEMPT_SOCKET'], os.environ['SPECROAD_ATTEMPT_SECRET'], command, **values)


def main(args):
    if not sys.platform.startswith('linux') or not hasattr(os, 'pidfd_open'):
        raise ValueError('Attempt control requires Linux pidfds')
    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'Cannot establish worker subreaper')
    # AF_UNIX paths are bounded independently of filesystem path limits.
    # The inherited TMPDIR may be a deep Apply/test directory: keep it for
    # the worker's ordinary temporary files, and use a short, private socket
    # directory on the supported Linux host. mkdtemp creates it with mode 0700.
    root = Path(tempfile.mkdtemp(prefix='sr-attempt-', dir='/tmp'))
    endpoint = str(root / 'control.sock')
    secret = uuid.uuid4().hex
    lock = threading.Lock()
    state = dict(active=None, completed=[], stopped=None)
    env = os.environ | dict(SPECROAD_ATTEMPT_SOCKET=endpoint, SPECROAD_ATTEMPT_SECRET=secret)
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(endpoint)
    listener.listen(4)
    listener.settimeout(0.2)
    child = subprocess.Popen([sys.executable, *args], env=env, start_new_session=True)
    quit_server = threading.Event()

    def serve():
        while not quit_server.is_set():
            try:
                connection, _ = listener.accept()
            except socket.timeout:
                continue
            with connection:
                try:
                    connection.settimeout(1)
                    _, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    if uid != os.getuid():
                        raise ValueError('Foreign supervisor client')
                    data = connection.makefile('rb').readline(65537)
                    if len(data) > 65536 or not data.endswith(b'\n'):
                        raise ValueError('Invalid supervisor request')
                    value = json.loads(data)
                    if type(value) is not dict:
                        raise ValueError('Invalid supervisor request shape')
                    if value.pop('secret', None) != secret:
                        raise ValueError('Foreign supervisor request')
                    command = value.pop('command', None)
                    if command in ('arm', 'complete', 'cancel') and (type(value.get('token')) is not str or not re.fullmatch('[0-9a-f]{32}', value['token'])):
                        raise ValueError('Invalid attempt identity')
                    with lock:
                        if command == 'arm' and set(value) == {'token', 'index', 'slot', 'nodeid', 'start'}:
                            if (any(type(value[k]) is not int or value[k] < 0 for k in ('index', 'slot', 'start'))
                                    or type(value['nodeid']) is not str or not value['nodeid'].startswith('tests/')
                                    or any(a['token'] == value['token'] for a in state['completed'])):
                                raise ValueError('Invalid attempt reservation')
                            if state['active'] is not None or state['stopped'] is not None:
                                raise ValueError('Worker already owns an attempt')
                            state['active'] = value
                            reply = dict(armed=value['token'])
                        elif command == 'complete' and set(value) == {'token', 'end'}:
                            active = state['active']
                            if (active is None or active['token'] != value['token'] or type(value['end']) is not int
                                    or value['end'] < active['start']):
                                raise ValueError('Completed attempt is not current')
                            state['completed'].append({**active, 'end': value['end']})
                            state['active'] = None
                            reply = dict(completed=value['token'])
                        elif command == 'cancel' and set(value) == {'token'}:
                            active = state['active']
                            if active is None or active['token'] != value['token']:
                                reply = dict(cancelled=False, reason='attempt_changed')
                            else:
                                end = terminate_tree()
                                reply = dict(cancelled=True, attempt={**active, 'end': end},
                                             completed=state['completed'], children_remaining=0)
                                state['stopped'] = reply
                        elif command == 'status' and not value:
                            reply = dict(active=state['active'], completed=state['completed'])
                        else:
                            raise ValueError('Invalid supervisor command')
                    connection.sendall(json.dumps(reply).encode() + b'\n')
                except (ValueError, TypeError, KeyError, OSError, TimeoutError) as error:
                    try:
                        connection.sendall(json.dumps(dict(error=str(error))).encode() + b'\n')
                    except OSError:
                        pass

    server = threading.Thread(target=serve, name='attempt-supervisor')
    server.start()
    try:
        while True:
            with lock:
                if state['stopped'] is not None:
                    return 137
                code = child.poll()
                if code is not None:
                    # Normal worker exit is distinct from confirmed operator
                    # cancellation. Leftover processes cannot outlive our scope.
                    terminate_tree()
                    return code if code >= 0 else 128 - code
            time.sleep(0.02)
    finally:
        quit_server.set()
        server.join(timeout=2)
        listener.close()
        (root / 'control.sock').unlink(missing_ok=True)
        root.rmdir()


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
