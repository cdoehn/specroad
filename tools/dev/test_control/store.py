"""Private, generation-bound control files; never a test or service launcher."""
from contextlib import contextmanager
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import tempfile
import time
import uuid

from dev.test_hosts.config import NAME, private_directory, read_json


def count(value):
    if type(value) is not int or not 0 <= value <= 256:
        raise ValueError('Worker count must be an integer in 0..256')
    return value


def counts(value):
    if type(value) is not dict or any(type(k) is not str or not NAME.fullmatch(k) for k in value):
        raise ValueError('Expected host names and worker counts')
    return {k: count(v) for k, v in value.items()}


def directory(home=None):
    return Path(home or os.environ.get('SPECROAD_TEST_CONTROL_HOME') or
                Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'specroad/test-control').expanduser().absolute()


def lane(repository, home=None):
    return directory(home) / sha256(str(Path(repository).resolve()).encode()).hexdigest()


def open_lock(path):
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or info.st_mode & 0o077:
        os.close(fd)
        raise ValueError('Unsafe control lock')
    return fd


@contextmanager
def guard(root):
    private_directory(root)
    fd = open_lock(root / 'guard')
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def write(path, value):
    fd, temporary = tempfile.mkstemp(prefix='.control-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def settings(root):
    path = root / 'settings.json'
    if not path.exists():
        return {}
    value = read_json(path)
    if type(value) is not dict or set(value) != {'version', 'workers'} or value['version'] != 1:
        raise ValueError('Invalid test-control settings')
    return counts(value['workers'])


def configure(repository, updates=None, *, home=None):
    root = lane(repository, home)
    with guard(root):
        value = settings(root)
        if updates is not None:
            value.update(counts(updates))
            write(root / 'settings.json', dict(version=1, workers=value))
        return value


def live(root):
    """A held owner lock is necessary; a leftover status file proves nothing."""
    path = root / 'owner'
    if not path.exists():
        return False
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        return False
    finally:
        os.close(fd)


def read_status(repository, *, home=None):
    root = lane(repository, home)
    if not root.exists():
        return None
    value = read_json(root / 'status.json') if (root / 'status.json').exists() else None
    if value is not None:
        value = dict(value, active=live(root))
        if value['repository'] != str(Path(repository).resolve()):
            raise ValueError('Foreign test-control target')
    return value


def change(repository, run, updates, *, home=None):
    root = lane(repository, home)
    with guard(root):
        status = read_status(repository, home=home)
        if status is None or not status['active'] or status['run'] != run:
            raise ValueError('The selected test run is no longer active')
        values = counts(updates)
        capacities = status['capacities']
        if not values or set(values) - capacities.keys() or any(v > capacities[k] for k, v in values.items()):
            raise ValueError('Unknown host or count exceeds the bound host capacity')
        request = read_json(root / 'request.json')
        if request['run'] != run:
            raise ValueError('Test run changed during request')
        requested = counts(request['workers'])
        requested.update(values)
        write(root / 'request.json', dict(version=1, run=run, workers=requested))
        return dict(run=run, requested=requested, acknowledged=False)


class Owner:
    """One native controller owns a lane until all workers have ended."""

    def __init__(self, repository, capacities, defaults, overrides=None, *, home=None):
        self.repository = str(Path(repository).resolve())
        self.root = lane(repository, home)
        self.capacities = counts(capacities)
        self.fd = None
        with guard(self.root):
            fd = open_lock(self.root / 'owner')
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BaseException:
                os.close(fd)
                raise
            self.fd = fd
            try:
                saved = settings(self.root)
                self.desired = counts(defaults) | saved | counts(overrides or {})
                if set(self.desired) != set(self.capacities) or any(v > self.capacities[k] for k, v in self.desired.items()):
                    raise ValueError('Requested workers exceed the checked host pool')
                self.run = uuid.uuid4().hex
                write(self.root / 'request.json', dict(version=1, run=self.run, workers=self.desired))
                self.publish({}, saved=saved, overrides=overrides or {})
            except BaseException:
                self.close()
                raise

    def refresh(self):
        value = read_json(self.root / 'request.json')
        if set(value) != {'version', 'run', 'workers'} or value['version'] != 1 or value['run'] != self.run:
            raise ValueError('Foreign or corrupt live worker request')
        desired = counts(value['workers'])
        if set(desired) != set(self.capacities) or any(v > self.capacities[k] for k, v in desired.items()):
            raise ValueError('Live worker request exceeds checked capacities')
        self.desired = desired
        return desired

    def publish(self, hosts, **extra):
        self.status = getattr(self, 'status', {}) | extra | dict(version=1,
            repository=self.repository, run=self.run, capacities=self.capacities,
            desired=self.desired, hosts=hosts, updated_at=time.time())
        write(self.root / 'status.json', self.status)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
