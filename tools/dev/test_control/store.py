"""Private, generation-bound control files; never a test or service launcher."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import tempfile
import time
import uuid

from dev.test_hosts.config import private_directory
from .files import inspect_directory, inspect_file, read_json
from .model import count, counts, directory, lane
# Preserve the established Python imports; the monitor uses only the reader.
from .view import live, read_status




def open_lock(path):
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        inspect_file(os.fstat(fd))
    except BaseException:
        os.close(fd)
        raise
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
    inspect_directory(path.parent)
    if os.path.lexists(path):
        inspect_file(path.lstat())
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
    if not os.path.lexists(path):
        return {}
    value = read_json(path)
    if type(value) is not dict or set(value) != {'version', 'workers'} or type(value['version']) is not int or value['version'] != 1:
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
                write(self.root / 'moves.json', dict(version=1, run=self.run, requests=[]))
                self.publish({}, saved=saved, overrides=overrides or {})
            except BaseException:
                self.close()
                raise

    def refresh(self):
        held, current = os.fstat(self.fd), (self.root / 'owner').lstat()
        if (held.st_dev, held.st_ino) != (current.st_dev, current.st_ino):
            raise ValueError('Live controller owner lock was replaced')
        value = read_json(self.root / 'request.json')
        if type(value) is not dict or set(value) != {'version', 'run', 'workers'} or type(value['version']) is not int or value['version'] != 1 or value['run'] != self.run:
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
