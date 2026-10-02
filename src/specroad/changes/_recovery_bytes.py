"""Descriptor-bound byte observations shared by recovery and its diagnosis."""
import os

from ..security import SafetyViolation
from ..security import paths as guards
from ..storage.byte_binding import fingerprint_reader
from .recovery_values import RecoveryError


def fingerprint_recovery_file(files, logical_path):
    parts = tuple(logical_path.split('/'))
    try:
        with files.directory(parts[:-1]) as directory:
            if directory is None:
                return None
            try:
                before = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                return None
            guards._regular(before)
            if before.st_nlink != 1:
                raise RecoveryError('recovery_linked_target_refused', path=logical_path, exit_code=7)
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW |
                         getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_CLOEXEC', 0),
                         dir_fd=directory)
            try:
                first = os.fstat(fd)
                guards._regular(first)
                if first.st_nlink != 1 or guards._signature(first) != guards._signature(before):
                    raise RecoveryError('recovery_target_changed', path=logical_path, exit_code=6)
                observed = fingerprint_reader(lambda n: os.read(fd, n), first.st_size)
                after = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
                if (guards._signature(first) != guards._signature(after)
                        or guards._signature(first) != guards._signature(os.fstat(fd))):
                    raise RecoveryError('recovery_target_changed', path=logical_path, exit_code=6)
                return {'identity': guards._identity(first), 'size': observed.size,
                        'sha256': observed.sha256, 'mode': first.st_mode & 0o7777}
            finally:
                os.close(fd)
    except RecoveryError:
        raise
    except SafetyViolation as error:
        raise RecoveryError('unsafe_recovery_target', path=logical_path, exit_code=7) from error
