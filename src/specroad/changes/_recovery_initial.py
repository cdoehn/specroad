"""Publish the initial rollback successor only after complete durable staging.

Linux O_TMPFILE keeps an interrupted derivative unnamed. The original journal
and before images remain the source of truth. A proc descriptor link publishes
exactly that inode without replacing an existing path; it has one link after
publication. Unsupported filesystem/proc operations fail without a named-write
fallback. No existing short file is inferred to be ours or repaired here.
"""
from hashlib import sha256
import os

from ..security import SafetyViolation
from ..security import paths as guards
from ..storage.byte_binding import fingerprint_reader
from .recovery_values import RecoveryError
from ._staging_files import _image


def write_initial_successor(directory, name, raw, *, before_publish):
    flag = getattr(os, 'O_TMPFILE', None)
    if flag is None:
        raise RecoveryError('recovery_atomic_stage_unavailable', exit_code=5)
    fd = os.open('.', flag | os.O_RDWR | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0),
                 0o600, dir_fd=directory)
    try:
        initial = os.fstat(fd)
        guards._regular(initial)
        identity = guards._identity(initial)
        if initial.st_nlink != 0 or initial.st_dev != os.fstat(directory).st_dev:
            raise RecoveryError('recovery_initial_stage_unbound', exit_code=6)
        view, offset = memoryview(raw), 0
        while offset < len(view):
            chunk = view[offset:offset + 65536]
            count = os.write(fd, chunk)
            if type(count) is not int or not 0 < count <= len(chunk):
                raise RecoveryError('recovery_initial_stage_short_write', exit_code=5)
            offset += count
        os.fsync(fd)
        written = os.fstat(fd)
        os.lseek(fd, 0, os.SEEK_SET)
        digest = sha256(raw).hexdigest()
        try:
            observed = fingerprint_reader(lambda size: os.read(fd, size), len(raw))
        except SafetyViolation as error:
            raise RecoveryError('recovery_initial_stage_changed', exit_code=6) from error
        if (guards._identity(written) != identity or written.st_nlink != 0
                or observed.sha256 != digest
                or guards._signature(os.fstat(fd)) != guards._signature(written)):
            raise RecoveryError('recovery_initial_stage_changed', exit_code=6)
        before_publish()
        current = os.fstat(fd)
        if current.st_nlink != 0 or guards._signature(current) != guards._signature(written):
            raise RecoveryError('recovery_initial_stage_changed', exit_code=6)
        try:
            # The only followed link is our kernel-owned descriptor reference,
            # never a project path. linkat creation refuses an occupied target.
            os.link('/proc/self/fd/' + str(fd), name, dst_dir_fd=directory,
                    follow_symlinks=True)
        except FileExistsError as error:
            raise RecoveryError('recovery_journal_successor_conflict', exit_code=6) from error
        os.fsync(directory)
        _image(directory, name, len(raw), digest, identity=identity)
        return identity
    finally:
        os.close(fd)
