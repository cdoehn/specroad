"""Native staging primitives with explicit file and directory durability boundaries.

Exclusive creation and readback never publish normative data. Keep partial
operational files for recovery; no retry, overwrite or unlink fallback.
"""
from hashlib import sha256
import os
from ..security import paths as guards
from ..storage.byte_binding import fingerprint_reader
from .staging_values import StagingError

_BLOCK = 65536


def _image(parent, name, size, digest, *, identity=None):
    """Hash the complete current regular file through a freshly verified descriptor."""
    before = os.stat(name, dir_fd=parent, follow_symlinks=False)
    guards._regular(before)
    if before.st_nlink != 1:
        raise StagingError('staging_hardlink_refused', path=name, exit_code=7)
    if before.st_size != size or (identity is not None and guards._identity(before) != identity):
        raise StagingError('staging_image_changed', path=name, exit_code=6)
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0)
                 | getattr(os, 'O_CLOEXEC', 0), dir_fd=parent)
    try:
        first = os.fstat(fd)
        guards._regular(first)
        if guards._signature(first) != guards._signature(before):
            raise StagingError('staging_image_changed', path=name, exit_code=6)
        observed = fingerprint_reader(lambda n: os.read(fd, n), size)
        after = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if (observed.size != size or observed.sha256 != digest
                or guards._signature(first) != guards._signature(after)
                or guards._signature(first) != guards._signature(os.fstat(fd))):
            raise StagingError('staging_image_changed', path=name, exit_code=6)
        return guards._identity(first)
    finally:
        os.close(fd)


def _write_new(parent, name, raw):
    """Exclusive private file, complete bounded writes, fsync, stable readback."""
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                 | getattr(os, 'O_CLOEXEC', 0), 0o600, dir_fd=parent)
    try:
        identity = guards._identity(os.fstat(fd))
        view = memoryview(raw)
        offset = 0
        while offset < len(view):
            chunk = view[offset:offset + _BLOCK]
            count = os.write(fd, chunk)
            if type(count) is not int or not 0 < count <= len(chunk):
                raise StagingError('staging_short_write', path=name, exit_code=5)
            offset += count
        os.fsync(fd)
        if os.fstat(fd).st_size != len(raw):
            raise StagingError('staging_incomplete_write', path=name, exit_code=5)
    finally:
        os.close(fd)
    os.fsync(parent)
    _image(parent, name, len(raw), sha256(raw).hexdigest(), identity=identity)
    return identity


def _names(directory, wanted):
    if set(os.listdir(directory)) != set(wanted):
        raise StagingError('staging_namespace_changed', exit_code=6)


def _images_on_disk(files, journal, identities=None):
    """Complete exact image namespace, including a deliberately empty before set."""
    entries = journal.data['files']
    prefix = tuple(journal.path.split('/')[:-1])
    for folder, path_key, size_key, hash_key in (
            ('staging', 'staging_path', 'after_size', 'after_sha256'),
            ('before', 'before_image_path', 'before_size', 'before_sha256')):
        values = [e for e in entries if e[path_key] is not None]
        with files.directory((*prefix, folder)) as fd:
            if fd is None:
                raise StagingError('staging_directory_missing', exit_code=5)
            _names(fd, [e[path_key].rsplit('/', 1)[-1] for e in values])
            for entry in values:
                path = entry[path_key]
                _image(fd, path.rsplit('/', 1)[-1], entry[size_key], entry[hash_key],
                       identity=None if identities is None else identities[path])
