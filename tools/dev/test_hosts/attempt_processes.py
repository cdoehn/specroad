"""Linux owned-process identity, freezing and complete descendant reaping."""
import os
from pathlib import Path
import signal
import time

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
