"""Lazy external work storage with a native, process-local Linux work lock.

This reserves storage for a trusted caller's work. It publishes no checkpoint,
confers no project write authority and never reclaims an orphan lock record.
"""

from contextlib import contextmanager
import os
from pathlib import Path
import secrets
import stat
import sys

from ..changes._lock_process import LinuxOwnerProbe
from ..model.canonical import canonical_json_bytes
from ..security import ProjectBoundary, SafetyViolation
from ..security import paths as guards
from .manifest import WorkManifest


_DIRECTORIES = ('checkpoints', 'objects', 'results')
_BINDING = 'root.json'
_LOCK = 'work-lock.json'


def _path(value):
    raw = os.fspath(value)
    if type(raw) is not str or not raw.startswith('/') or raw.startswith('//'):
        raise SafetyViolation('An absolute external work path is required')
    guards._parts(raw[1:])
    return Path(raw)


def _private(info, *, directory=False):
    guards._regular(info, directory=directory)
    if (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077
            or (not directory and info.st_nlink != 1)):
        raise SafetyViolation('Work storage must be private and exclusively owned')


class WorkDirectory:
    """A lazy location for one trusted initial manifest, not a resume verifier.

    Supply every protected project/input/output directory, including parents of
    output files. Merely declaring a location creates no directories or locks.
    Only for_checkpoint() allocates storage. Native failures propagate so the
    caller can try a safe in-memory completion before declaring a blocker.
    """

    def __init__(self, manifest, *, protected_roots, directory=None, temporary_directory=None):
        if type(manifest) is not WorkManifest:
            raise ValueError('A trusted checked work manifest is required')
        if type(protected_roots) is not tuple or not protected_roots or any(
                type(boundary) is not ProjectBoundary for boundary in protected_roots):
            raise ValueError('Explicit protected project/input/output boundaries are required')
        value = manifest.as_dict()
        self._work_id = value['work_id']
        self._initial_hash = value['checkpoint_sha256']
        self._protected = protected_roots
        self._requested = None if directory is None else _path(directory)
        self._temporary = None if temporary_directory is None else _path(temporary_directory)
        self._path = None

    @property
    def path(self):
        """Actual allocated path, or None before storage was needed."""
        return self._path

    def _outside(self, path):
        for boundary in self._protected:
            boundary._check_root()
            if path.is_relative_to(boundary.root) or boundary.root.is_relative_to(path):
                raise SafetyViolation('Work and protected paths overlap')

    @contextmanager
    def for_checkpoint(self):
        """Reserve a guarded root; exiting releases only our exact live owner.

        Retains all work files, even on failure. No work.json/Code 8 or durable
        continuation is claimed by this storage-only preparation step.
        """
        if not sys.platform.startswith('linux') or not guards._HAS_SAFE_OPEN:
            raise SafetyViolation('Native work locking is unavailable')
        path = self._path or self._requested
        exclusive = False
        if path is None:
            # Reading the preference does not probe-write into a project temp dir.
            parent = self._temporary or _path(os.environ.get('TMPDIR') or '/tmp')
            path = parent / ('specroad-work-' + secrets.token_hex(16))
            exclusive = True
        self._outside(path)
        with _HeldWorkRoot(self, path, exclusive=exclusive) as held:
            self._path = path
            yield held


class _HeldWorkRoot:
    def __init__(self, location, path, *, exclusive):
        self.path = path
        self.work_id = location._work_id
        self._location = location
        self._exclusive = exclusive
        self._fds = []
        self._entries = []
        self._pid = os.getpid()
        self._locked = False
        self._owner = None

    def _adopt(self, fd):
        try:
            self._fds.append(fd)
        except BaseException:
            os.close(fd)
            raise
        return fd

    def _directory(self, parent, name):
        before = os.stat(name, dir_fd=parent, follow_symlinks=False)
        guards._regular(before, directory=True)
        fd = self._adopt(os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                 dir_fd=parent))
        identity = guards._identity(before)
        if guards._identity(os.fstat(fd)) != identity:
            raise SafetyViolation('Work directory changed while opening')
        self._entries.append((parent, name, fd, identity))
        return fd

    def _check_path(self):
        if not self._fds or os.getpid() != self._pid:
            raise SafetyViolation('Work handle is not active in this process')
        self._location._outside(self.path)
        for parent, name, fd, identity in self._entries:
            current = os.stat(name, dir_fd=parent, follow_symlinks=False)
            guards._regular(current, directory=True)
            if guards._identity(current) != identity or guards._identity(os.fstat(fd)) != identity:
                raise SafetyViolation('Work directory changed during use')
        if hasattr(self, '_root'):
            _private(os.fstat(self._root), directory=True)
        for fd in getattr(self, '_children', ()):
            _private(os.fstat(fd), directory=True)

    def _read(self, name):
        self._check_path()
        before = os.stat(name, dir_fd=self._root, follow_symlinks=False)
        _private(before)
        if before.st_size > 65536:
            raise SafetyViolation('Work control record is too large')
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self._root)
        try:
            if guards._signature(os.fstat(fd)) != guards._signature(before):
                raise SafetyViolation('Work record changed while opening')
            data = bytearray()
            while len(data) <= before.st_size:
                chunk = os.read(fd, min(8192, before.st_size + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
            current = os.stat(name, dir_fd=self._root, follow_symlinks=False)
            if (len(data) != before.st_size or guards._signature(current) != guards._signature(before)
                    or guards._signature(os.fstat(fd)) != guards._signature(before)):
                raise SafetyViolation('Work record changed while reading')
            self._check_path()
            return bytes(data), guards._identity(before)
        finally:
            os.close(fd)

    def _create(self, name, raw):
        self._check_path()
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=self._root)
        try:
            offset = 0
            while offset < len(raw):
                n = os.write(fd, raw[offset:])
                if type(n) is not int or not 0 < n <= len(raw) - offset:
                    raise SafetyViolation('Work record write made no valid progress')
                offset += n
            os.fsync(fd)
            identity = guards._identity(os.fstat(fd))
            os.fsync(self._root)
        finally:
            os.close(fd)
        if self._read(name) != (raw, identity):
            raise SafetyViolation('Work record changed after publication')
        return identity

    def __enter__(self):
        import fcntl
        self._fcntl = fcntl
        try:
            parent = self._adopt(os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW))
            parts = guards._parts(str(self.path)[1:])
            for name in parts[:-1]:
                parent = self._directory(parent, name)
            self._check_path()
            try:
                os.mkdir(parts[-1], 0o700, dir_fd=parent)
                os.fsync(parent)
            except FileExistsError:
                if self._exclusive:
                    raise
            self._root = self._directory(parent, parts[-1])
            self._check_path()
            fcntl.flock(self._root, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._locked = True
            self._check_path()
            info = os.fstat(self._root)
            self._binding = canonical_json_bytes({'format_version': 'work-root-v1',
                'work_id': self.work_id, 'initial_checkpoint_sha256': self._location._initial_hash,
                'device': str(info.st_dev), 'inode': str(info.st_ino)})
            names = set(os.listdir(self._root))
            if names:
                # Never infer authorization from PID, hostname or an unlocked fd.
                if names != {_BINDING, *_DIRECTORIES}:
                    raise SafetyViolation('Foreign, incomplete or locked work root')
                raw, self._binding_inode = self._read(_BINDING)
                if raw != self._binding:
                    raise SafetyViolation('Work root belongs to a different bound order')
            else:
                self._binding_inode = self._create(_BINDING, self._binding)
                for name in _DIRECTORIES:
                    self._check_path()
                    os.mkdir(name, 0o700, dir_fd=self._root)
                os.fsync(self._root)
            self._children = []
            for name in _DIRECTORIES:
                self._children.append(self._directory(self._root, name))
            self._check_path()
            owner = LinuxOwnerProbe().current()
            if owner.host_id is None or owner.process_start_id is None:
                raise SafetyViolation('Work lock owner cannot be verified')
            record = canonical_json_bytes({'format_version': 'work-lock-v1',
                'work_id': self.work_id, 'owner_nonce': secrets.token_hex(16), **owner.as_dict()})
            inode = self._create(_LOCK, record)
            self._owner = (record, inode)
            self.check()
            return self
        except BaseException:
            self._close()
            raise

    def check(self):
        self._check_path()
        if not self._locked or self._owner is None:
            raise SafetyViolation('No active work lock')
        if self._read(_BINDING) != (self._binding, self._binding_inode):
            raise SafetyViolation('Work identity changed')
        if self._read(_LOCK) != self._owner:
            raise SafetyViolation('Work lock owner changed')
        return True

    def __exit__(self, *args):
        try:
            if os.getpid() == self._pid:
                self.check()
                os.unlink(_LOCK, dir_fd=self._root)
                os.fsync(self._root)
        finally:
            self._close()

    def _close(self):
        try:
            if self._locked and self._pid == os.getpid():
                self._fcntl.flock(self._root, self._fcntl.LOCK_UN)
        finally:
            self._locked = False
            while self._fds:
                os.close(self._fds.pop())

    def __reduce__(self):
        raise TypeError('Live work locks cannot be serialized')

    def __copy__(self):
        raise TypeError('Live work locks cannot be copied')

    def __deepcopy__(self, memo):
        raise TypeError('Live work locks cannot be copied')
