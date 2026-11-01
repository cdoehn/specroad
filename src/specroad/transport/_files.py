"""Stable passive inputs and explicit unlinked host boundaries, never discovery."""
from hashlib import sha256
import os
from pathlib import Path
import stat

from ..security import ProjectBoundary
from ..security.resource_access import opened_resource
from .snapshots import TransportFailure


def require(condition, reason, code=7):
    if not condition:
        raise TransportFailure(code, reason=reason)


def absolute(value):
    require(isinstance(value, (str, Path)), 'absolute_transport_path_required', 2)
    path = Path(value)
    require(path.is_absolute() and '..' not in path.parts, 'absolute_transport_path_required', 2)
    return path


def directory(value, *, owned=False):
    path = absolute(value)
    for parent in (*reversed(path.parents), path):
        info = parent.lstat()
        require(stat.S_ISDIR(info.st_mode), 'unsafe_transport_directory')
    if owned:
        info = path.lstat()
        require(info.st_uid == os.getuid() and not info.st_mode & stat.S_IWOTH,
                'unsafe_transport_output_owner')
    return ProjectBoundary(path)


def overlap(left, right):
    return left == right or left in right.parents or right in left.parents


class PassiveFile:
    """Own a byte capture; subsequent uses recheck identity and complete bytes."""

    def __init__(self, path, *, expected_sha256=None, limit=256 * 1024 * 1024):
        self.path = absolute(path)
        self.boundary = directory(self.path.parent)
        self.limit = limit
        self.raw, self.identity = self._read()
        self.sha256 = sha256(self.raw).hexdigest()
        if expected_sha256 is not None:
            from ._contract import valid_digest
            require(valid_digest(expected_sha256), 'external_transport_hash_required', 2)
            require(self.sha256 == expected_sha256, 'transport_input_hash_mismatch', 6)

    def _read(self):
        with opened_resource(self.boundary, self.path.name) as (fd, info):
            require(info.st_nlink == 1, 'linked_transport_input')
            require(info.st_size <= self.limit, 'transport_input_limit')
            chunks, size = [], 0
            while True:
                raw = os.read(fd, min(1024 * 1024, self.limit - size + 1))
                if not raw:
                    break
                size += len(raw)
                require(size <= self.limit, 'transport_input_limit')
                chunks.append(raw)
            return b''.join(chunks), (info.st_dev, info.st_ino)

    def verify_current(self):
        raw, identity = self._read()
        require(raw == self.raw and identity == self.identity, 'transport_input_changed', 6)
