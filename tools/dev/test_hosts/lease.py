"""Per-user host slots shared across Apply lines and held by the worker itself."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import stat
import tempfile

from .config import private_directory


class Lease:
    def __init__(self, limit, *, directory=None):
        if type(limit) is not int or not 1 <= limit <= 256:
            raise ValueError('Invalid host slot budget')
        self.fd = None
        root = private_directory(directory or Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'specroad/test-host-slots')
        guard = os.open(root / 'guard', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        held = []
        try:
            fcntl.flock(guard, fcntl.LOCK_EX)
            config = root / 'budget.json'
            if config.is_symlink():
                raise ValueError('Linked host budget')
            old = json.loads(config.read_text()) if config.exists() else limit
            if config.exists() and (not stat.S_ISREG(config.stat().st_mode) or config.stat().st_nlink != 1):
                raise ValueError('Unsafe host budget file')
            if type(old) is not int or not 1 <= old <= 256:
                raise ValueError('Invalid stored host budget')
            if old != limit:
                # Changing a quota while any old worker lives could oversubscribe it.
                for i in range(old):
                    fd = os.open(root / str(i), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
                    held.append(fd)
                    try:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        raise ValueError('Host budget change requires all slots to be idle') from None
            fd, temporary = tempfile.mkstemp(prefix='.budget-', dir=root)
            try:
                with os.fdopen(fd, 'w') as stream:
                    stream.write(json.dumps(limit)); stream.flush(); os.fsync(stream.fileno())
                os.replace(temporary, config)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            for fd in held:
                os.close(fd)
            held.clear()
            for i in range(limit):
                fd = os.open(root / str(i), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    os.close(fd)
                else:
                    self.fd, self.slot = fd, i
                    break
            if self.fd is None:
                raise ValueError('All host slots are occupied; no oversubscribed test worker started')
        finally:
            for fd in held:
                os.close(fd)
            os.close(guard)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def io_priority():
    # Best-effort class, lowest priority; inherited by test subprocesses.
    result = subprocess.run(['ionice', '-c', '2', '-n', '7', '-p', str(os.getpid())],
                            capture_output=True, timeout=10, check=False)
    if result.returncode:
        raise ValueError('Cannot establish low test I/O priority')
    return {'class': 2, 'priority': 7}
