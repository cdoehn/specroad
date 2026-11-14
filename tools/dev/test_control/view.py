"""Read-only, generation-aware live status shared by CLI and monitor."""
import fcntl
import os
from pathlib import Path

from .files import inspect_directory, inspect_file, read_json
from .model import lane


def live(root):
    """A held owner lock is necessary; a leftover status file proves nothing."""
    path = root / 'owner'
    inspect_directory(root)
    if not os.path.lexists(path):
        return False
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        inspect_file(os.fstat(fd))
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        return False
    finally:
        os.close(fd)


def read_status(repository, *, home=None):
    root = lane(repository, home)
    if not os.path.lexists(root):
        return None
    inspect_directory(root)
    value = read_json(root / 'status.json') if os.path.lexists(root / 'status.json') else None
    if value is not None:
        value = dict(value, active=live(root))
        if value['repository'] != str(Path(repository).resolve()):
            raise ValueError('Foreign test-control target')
        latest = read_json(root / 'status.json')
        if latest['run'] != value['run']:
            raise ValueError('Live test generation changed while reading status')
    return value
