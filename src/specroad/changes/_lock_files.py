"""Descriptor-bound lock storage. All three lock kinds share the root-inode mutex.

Linux local filesystems are the native scope. flock is advisory: independent
noncooperating writers or a hostile filesystem are not sandboxed. There is no
persistent mutex pathname to unlink and accidentally split into two mutexes.
"""
from __future__ import annotations
from contextlib import contextmanager
import errno
import os
import stat
import sys
from ..security import ProjectBoundary, SafetyViolation
from ..security import paths as guards
from .lock_values import ProjectLockError, LockRecord, MAX_LOCK_BYTES, LOCK_PATH


def identity(info):
    return {'device': str(info.st_dev), 'inode': str(info.st_ino)}


class LockFiles:
    def __init__(self, root):
        self.boundary = ProjectBoundary(root)
        self.root_fd = None
        self.held = False
        self.creator_pid = os.getpid()
        self._fcntl = None

    def __enter__(self):
        if not sys.platform.startswith('linux') or not guards._HAS_SAFE_OPEN:
            raise ProjectLockError('native_lock_unavailable')
        self.boundary._check_root()
        self.root_fd = os.open(self.boundary.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0))
        try:
            self.check_root()
        except BaseException:
            os.close(self.root_fd); self.root_fd = None
            raise
        return self

    def check_root(self):
        self.boundary._check_root()
        if self.root_fd is None or guards._identity(os.fstat(self.root_fd)) != self.boundary._root_identity:
            raise ProjectLockError('lock_root_changed', exit_code=6)

    def acquire(self):
        if self.creator_pid != os.getpid():
            raise ProjectLockError('inherited_lock_handle', exit_code=7)
        import fcntl
        self._fcntl = fcntl
        try:
            fcntl.flock(self.root_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno in (errno.EAGAIN, errno.EACCES):
                raise ProjectLockError('project_lock_busy') from error
            raise ProjectLockError('native_lock_unavailable') from error
        self.held = True
        self.check_root()

    def __exit__(self, *args):
        if self.root_fd is not None:
            try:
                # Forked children must never issue LOCK_UN on the parent's OFD.
                if self.held and self.creator_pid == os.getpid():
                    self._fcntl.flock(self.root_fd, self._fcntl.LOCK_UN)
            finally:
                os.close(self.root_fd); self.root_fd = None; self.held = False

    def require_held(self):
        if not self.held or self.creator_pid != os.getpid():
            raise ProjectLockError('lock_not_held_by_this_process', exit_code=7)
        self.check_root()

    @contextmanager
    def directory(self, parts, *, create=False):
        self.check_root()
        descriptors, opened = [], []
        parent = self.root_fd
        try:
            for name in parts:
                try:
                    before = os.stat(name, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    if not create:
                        yield None
                        return
                    self.require_held()
                    try:
                        os.mkdir(name, mode=0o700, dir_fd=parent)
                        os.fsync(parent)
                    except FileExistsError:
                        pass
                    before = os.stat(name, dir_fd=parent, follow_symlinks=False)
                guards._regular(before, directory=True)
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0), dir_fd=parent)
                descriptors.append(child)
                if guards._identity(os.fstat(child)) != guards._identity(before):
                    raise ProjectLockError('lock_directory_changed', exit_code=6)
                try:
                    os.stat('specroad.json', dir_fd=child, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise ProjectLockError('nested_lock_project', exit_code=7)
                opened.append((parent, name, child, guards._identity(before)))
                parent = child
            yield parent
            for parent, name, child, expected in opened:
                now = os.stat(name, dir_fd=parent, follow_symlinks=False)
                guards._regular(now, directory=True)
                if guards._identity(now) != expected or guards._identity(os.fstat(child)) != expected:
                    raise ProjectLockError('lock_directory_changed', exit_code=6)
            self.check_root()
        except OSError as error:
            if error.errno in (errno.ELOOP, errno.ENOTDIR):
                raise ProjectLockError('unsafe_lock_path', exit_code=7) from error
            raise
        finally:
            for fd in reversed(descriptors):
                os.close(fd)

    def _read(self, parent, name):
        before = os.stat(name, dir_fd=parent, follow_symlinks=False)
        guards._regular(before)
        if before.st_nlink != 1 or before.st_size > MAX_LOCK_BYTES:
            raise ProjectLockError('unsafe_lock_record', exit_code=7)
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_CLOEXEC', 0), dir_fd=parent)
        try:
            first = os.fstat(fd); guards._regular(first)
            if first.st_nlink != 1 or guards._signature(first) != guards._signature(before):
                raise ProjectLockError('lock_record_changed', exit_code=6)
            data = bytearray()
            while len(data) <= MAX_LOCK_BYTES:
                chunk = os.read(fd, min(8192, MAX_LOCK_BYTES + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
            after = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if (len(data) != first.st_size or guards._signature(os.fstat(fd)) != guards._signature(first)
                    or guards._signature(after) != guards._signature(first)):
                raise ProjectLockError('lock_record_changed', exit_code=6)
            return bytes(data), guards._identity(first)
        finally:
            os.close(fd)

    def read_record(self):
        with self.directory(('.specroad', 'locks')) as directory:
            if directory is None:
                return None, None
            names = sorted(os.listdir(directory))
            if not names:
                return None, None
            if names != ['project.json']:
                raise ProjectLockError('unknown_lock_entries')
            raw, ident = self._read(directory, 'project.json')
            return LockRecord(raw), ident

    def create_record(self, record):
        self.require_held()
        with self.directory(('.specroad', 'locks'), create=True) as directory:
            if os.listdir(directory):
                raise ProjectLockError('lock_recovery_required')
            # O_EXCL publishes only this owner, never truncates a prior record.
            # Interrupted writes leave a blocker; not a false absence of owner.
            fd = os.open('project.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0), 0o600, dir_fd=directory)
            try:
                data = record.source_bytes
                offset = 0
                while offset < len(data):
                    n = os.write(fd, data[offset:])
                    if n <= 0:
                        raise ProjectLockError('lock_record_write_incomplete', mutation_possible=True)
                    offset += n
                os.fsync(fd)
                ident = guards._identity(os.fstat(fd))
                os.fsync(directory)
            finally:
                os.close(fd)
        self.check_root()
        return ident

    def remove_record(self, expected, expected_identity):
        self.require_held()
        with self.directory(('.specroad', 'locks')) as directory:
            if directory is None:
                raise ProjectLockError('lock_record_missing', exit_code=6)
            raw, ident = self._read(directory, 'project.json')
            if raw != expected.source_bytes or ident != expected_identity:
                raise ProjectLockError('lock_owner_changed', exit_code=6)
            self.check_root()
            os.unlink('project.json', dir_fd=directory)
            os.fsync(directory)

    def append_audit(self, event_id, phase, raw):
        """Create one immutable operational audit event; never replace history."""
        from uuid import UUID
        if str(UUID(event_id)) != event_id or phase not in ('intent', 'completed'):
            raise ProjectLockError('invalid_lock_audit_identity', exit_code=2)
        if type(raw) is not bytes or not 0 < len(raw) <= MAX_LOCK_BYTES:
            raise ProjectLockError('invalid_lock_audit_data', exit_code=2)
        self.require_held()
        with self.directory(('.specroad', 'recovery', 'lock-audit'), create=True) as directory:
            name = event_id + '.' + phase + '.json'
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0), 0o600, dir_fd=directory)
            try:
                offset = 0
                while offset < len(raw):
                    n = os.write(fd, raw[offset:])
                    if n <= 0:
                        raise ProjectLockError('lock_audit_write_incomplete', mutation_possible=True)
                    offset += n
                os.fsync(fd)
                os.fsync(directory)
            finally:
                os.close(fd)
        return '.specroad/recovery/lock-audit/' + name

    def journal_entries(self):
        found = []
        with self.directory(('.specroad',)) as directory:
            if directory is not None:
                for name in sorted(os.listdir(directory)):
                    info = os.stat(name, dir_fd=directory, follow_symlinks=False)
                    guards._regular(info, directory=stat.S_ISDIR(info.st_mode))
                    if name not in ('locks', 'transactions', 'recovery', 'cache', 'requests') or not stat.S_ISDIR(info.st_mode):
                        found.append('.specroad/' + name)
        for folder in ('transactions', 'recovery'):
            with self.directory(('.specroad', folder)) as directory:
                if directory is None:
                    continue
                for name in sorted(os.listdir(directory)):
                    info = os.stat(name, dir_fd=directory, follow_symlinks=False)
                    guards._regular(info, directory=stat.S_ISDIR(info.st_mode))
                    # Only the explicit completed receipt / lock-audit namespaces
                    # are outside active journals; no self-declared terminal state.
                    reserved = (folder == 'transactions' and name == 'receipts') or (folder == 'recovery' and name == 'lock-audit')
                    if reserved and stat.S_ISDIR(info.st_mode):
                        continue
                    found.append('.specroad/' + folder + '/' + name)
        return tuple(found)
