"""Private work-root lease and guarded work files; never a project writer lock.

The Linux process observation is shared read-only metadata. Lock acquisition,
records, protected paths and cleanup belong exclusively to the external work root.
"""

import os
import secrets
import stat

from ..changes._lock_process import LinuxOwnerProbe
from ..model.canonical import canonical_json_bytes
from ..security import SafetyViolation
from ..security import paths as guards


_DIRECTORIES = ('checkpoints', 'objects', 'results')
_BINDING = 'root.json'
_LOCK = 'work-lock.json'
_CURRENT = 'work.json'


def _private(info, *, directory=False):
    guards._regular(info, directory=directory)
    if (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077
            or (not directory and info.st_nlink != 1)):
        raise SafetyViolation('Work storage must be private and exclusively owned')


class _HeldWorkRoot:
    def __init__(self, location, path, *, exclusive, inspection=False):
        self.path = path
        self.work_id = location._work_id
        self._location = location
        self._exclusive = exclusive
        self._inspection = inspection
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
            info = os.fstat(self._root)
            _private(info, directory=True)
            expected = self._location._allocated_identity
            if expected is not None and guards._identity(info) != expected:
                raise SafetyViolation('Previously allocated work root changed')
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

    def _validate_tree(self, directory):
        """Inspect retained entry types/ownership without reading payload bytes.

        Iterative descriptor traversal keeps only the active directory chain.
        Payload readers/writers still need their own current path/hash checks.
        """
        stack = []
        seen = {guards._identity(os.fstat(directory))}
        def enter(fd, parent=None, name=None):
            iterator = None
            try:
                signature = guards._signature(os.fstat(fd))
                iterator = os.scandir(fd)
                stack.append((fd, iterator, signature, parent, name))
            except BaseException:
                if iterator is not None:
                    iterator.close()
                if parent is not None:
                    os.close(fd)
                raise
        try:
            enter(directory)
            while stack:
                self._check_path()
                parent, iterator, signature, ancestor, basename = stack[-1]
                entry = next(iterator, None)
                if entry is None:
                    if guards._signature(os.fstat(parent)) != signature:
                        raise SafetyViolation('Work payload directory changed during inspection')
                    if ancestor is not None:
                        current = os.stat(basename, dir_fd=ancestor, follow_symlinks=False)
                        if guards._signature(current) != signature:
                            raise SafetyViolation('Work payload path changed during inspection')
                    stack.pop()
                    iterator.close()
                    if ancestor is not None:
                        os.close(parent)
                    continue
                guards._parts(entry.name)
                before = os.stat(entry.name, dir_fd=parent, follow_symlinks=False)
                is_directory = stat.S_ISDIR(before.st_mode)
                _private(before, directory=is_directory)
                flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                if is_directory:
                    flags |= os.O_DIRECTORY
                fd = os.open(entry.name, flags, dir_fd=parent)
                try:
                    if guards._signature(os.fstat(fd)) != guards._signature(before):
                        raise SafetyViolation('Work payload entry changed while opening')
                    if is_directory:
                        identity = guards._identity(before)
                        if identity in seen or any(identity == b._root_identity for b in self._location._protected):
                            raise SafetyViolation('Aliased work payload directory')
                        seen.add(identity)
                        nested = fd
                        fd = None  # enter owns the descriptor, including on failure.
                        enter(nested, parent, entry.name)
                    else:
                        current = os.stat(entry.name, dir_fd=parent, follow_symlinks=False)
                        if guards._signature(current) != guards._signature(before):
                            raise SafetyViolation('Work payload entry changed during inspection')
                finally:
                    if fd is not None:
                        os.close(fd)
        finally:
            while stack:
                fd, iterator, _, ancestor, _ = stack.pop()
                iterator.close()
                if ancestor is not None:
                    os.close(fd)

    def __enter__(self):
        import fcntl
        self._fcntl = fcntl
        try:
            parent = self._adopt(os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW))
            parts = guards._parts(str(self.path)[1:])
            for name in parts[:-1]:
                parent = self._directory(parent, name)
            self._check_path()
            if self._location._allocated_identity is None and not self._inspection:
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
                required = {_BINDING, *_DIRECTORIES}
                optional = {_CURRENT, _LOCK} if self._inspection else {_CURRENT}
                if not required <= names or not names <= required | optional:
                    raise SafetyViolation('Foreign, incomplete or locked work root')
                raw, self._binding_inode = self._read(_BINDING)
                if raw != self._binding:
                    raise SafetyViolation('Work root belongs to a different bound order')
            else:
                if self._inspection:
                    raise SafetyViolation('No bound work root to inspect')
                self._binding_inode = self._create(_BINDING, self._binding)
                for name in _DIRECTORIES:
                    self._check_path()
                    os.mkdir(name, 0o700, dir_fd=self._root)
                os.fsync(self._root)
            self._children = []
            for name in _DIRECTORIES:
                self._children.append(self._directory(self._root, name))
            self._check_path()
            for fd in self._children:
                self._validate_tree(fd)
            if _CURRENT in names:
                self._read(_CURRENT)
            if self._inspection:
                # A data-only inspection never steals/removes a retained owner.
                self._owner = self._read(_LOCK) if _LOCK in names else None
                self.check()
                return self
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
        if not self._locked or (self._owner is None and not self._inspection):
            raise SafetyViolation('No active work lock')
        if self._read(_BINDING) != (self._binding, self._binding_inode):
            raise SafetyViolation('Work identity changed')
        try:
            owner = self._read(_LOCK)
        except FileNotFoundError:
            if not self._inspection or self._owner is not None:
                raise
            owner = None
        if owner != self._owner:
            raise SafetyViolation('Work lock owner changed')
        return True

    def __exit__(self, *args):
        try:
            if os.getpid() == self._pid:
                self.check()
                if not self._inspection:
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
