"""Shared worker-intent values and canonical lane identity; no mutable state."""
from hashlib import sha256
import os
from pathlib import Path

from dev.test_hosts.config import NAME


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
