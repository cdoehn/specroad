"""Owned bootstrap staging and no-replace publication on native Linux filesystems.

The root-inode mutex is advisory, as for existing project transactions. This
module never interprets stored journal data as authority to execute or delete.
Recovery validates the closed journal and all actual owned bytes before use.
"""
from contextlib import contextmanager
from hashlib import sha256
import ctypes
import errno
import os
import stat

from ..model.canonical import canonical_json_bytes
from ..security import SafetyViolation
from ..security import paths as guards

STAGING = '.specroad-bootstrap'
COMPLETED = ('.specroad', 'recovery', 'init-bootstrap')


class BootstrapError(Exception):
    def __init__(self, reason, *, exit_code=6, path=None, mutation_possible=False):
        super().__init__(reason)
        self.reason = reason
        self.exit_code = exit_code
        self.path = path
        self.mutation_possible = mutation_possible


def rename_function():
    """Resolve the platform primitive before any write; no replacing fallback."""
    try:
        function = ctypes.CDLL(None, use_errno=True).renameat2
    except AttributeError as error:
        raise OSError(errno.ENOTSUP, 'Native no-replace publication unavailable') from error
    function.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    function.restype = ctypes.c_int
    return function


def _rename_native(function, source_fd, source, target_fd, target):
    if function(source_fd, os.fsencode(source), target_fd, os.fsencode(target), 1) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), target)


def rename_new(function, source_fd, source, target_fd, target):
    """Publish or roll back one project payload unit, never control metadata."""
    _rename_native(function, source_fd, source, target_fd, target)
    os.fsync(target_fd)
    os.fsync(source_fd)


def info_at(parent, name):
    try:
        return os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return None


def identity(info):
    return list(guards._identity(info))


@contextmanager
def directory(parent, parts=()):
    descriptors = []
    try:
        for name in parts:
            before = os.stat(name, dir_fd=parent, follow_symlinks=False)
            guards._regular(before, directory=True)
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW |
                         getattr(os, 'O_CLOEXEC', 0), dir_fd=parent)
            descriptors.append(fd)
            if identity(os.fstat(fd)) != identity(before):
                raise BootstrapError('bootstrap_directory_changed', path=name)
            parent = fd
        yield parent
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def metadata(info, raw=None):
    value = {'identity': identity(info), 'mode': stat.S_IMODE(info.st_mode),
             'kind': 'directory' if stat.S_ISDIR(info.st_mode) else 'file'}
    if raw is not None:
        value.update(size=len(raw), sha256=sha256(raw).hexdigest())
    return value


def check_entry(parent, name, expected):
    info = os.stat(name, dir_fd=parent, follow_symlinks=False)
    guards._regular(info, directory=expected['kind'] == 'directory')
    if identity(info) != expected['identity'] or stat.S_IMODE(info.st_mode) != expected['mode']:
        raise BootstrapError('bootstrap_owned_entry_changed', path=name)
    if expected['kind'] == 'file' and (info.st_nlink != 1 or info.st_size != expected['size']):
        raise BootstrapError('bootstrap_owned_file_changed', path=name)
    return info


def verify_tree(parent, inventory, prefix='', *, receipt_identity=None):
    """Exact names, identities and bytes; no unlisted entry is read or removed."""
    children = {p[len(prefix):].split('/')[0] for p in inventory if p.startswith(prefix)}
    actual = set(os.listdir(parent))
    if receipt_identity is not None and prefix == '.specroad/recovery/':
        receipt = info_at(parent, COMPLETED[-1])
        if receipt is None or identity(receipt) != receipt_identity:
            raise BootstrapError('bootstrap_receipt_changed')
        guards._regular(receipt, directory=True)
        actual.remove(COMPLETED[-1])
    if actual != children:
        raise BootstrapError('bootstrap_inventory_changed', path=prefix)
    for name in sorted(children):
        path = prefix + name
        expected = inventory[path]
        before = check_entry(parent, name, expected)
        if expected['kind'] == 'directory':
            with directory(parent, (name,)) as child:
                verify_tree(child, inventory, path + '/', receipt_identity=receipt_identity)
        else:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0), dir_fd=parent)
            try:
                if guards._signature(os.fstat(fd)) != guards._signature(before):
                    raise BootstrapError('bootstrap_file_changed', path=path)
                digest = sha256(); size = 0
                while size <= expected['size']:
                    block = os.read(fd, min(65536, expected['size'] + 1 - size))
                    if not block:
                        break
                    digest.update(block); size += len(block)
                if size != expected['size'] or digest.hexdigest() != expected['sha256']:
                    raise BootstrapError('bootstrap_file_changed', path=path)
                if guards._signature(os.fstat(fd)) != guards._signature(before):
                    raise BootstrapError('bootstrap_file_changed', path=path)
            finally:
                os.close(fd)
        if guards._signature(check_entry(parent, name, expected)) != guards._signature(before):
            raise BootstrapError('bootstrap_entry_changed', path=path)


def verify_unit(parent, name, inventory, path, *, receipt_identity=None):
    expected = inventory[path]
    check_entry(parent, name, expected)
    if expected['kind'] == 'directory':
        with directory(parent, (name,)) as child:
            verify_tree(child, inventory, path + '/', receipt_identity=receipt_identity)
    else:
        # Same bounded byte check as for a tree, without requiring an otherwise
        # empty repository parent. This one file is always the final config.
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            before = os.fstat(fd)
            if identity(before) != expected['identity']:
                raise BootstrapError('bootstrap_file_changed', path=path)
            raw = bytearray()
            while len(raw) <= expected['size']:
                block = os.read(fd, min(65536, expected['size'] + 1 - len(raw)))
                if not block: break
                raw.extend(block)
            if len(raw) != expected['size'] or sha256(raw).hexdigest() != expected['sha256']:
                raise BootstrapError('bootstrap_file_changed', path=path)
            if guards._signature(os.fstat(fd)) != guards._signature(before):
                raise BootstrapError('bootstrap_file_changed', path=path)
        finally:
            os.close(fd)
        check_entry(parent, name, expected)


class BootstrapTree:
    def __init__(self, held, function, reused):
        self.held = held
        self.function = function
        self.reused = reused
        self.inventory = {}
        self.stage_identity = None
        self.fd = None
        self.units = []
        self.committed = False
        self.stage_parts = (STAGING,)

    def check(self):
        self.held.require_held()
        if self.fd is None or identity(os.fstat(self.fd)) != self.stage_identity:
            raise BootstrapError('bootstrap_stage_changed')
        with directory(self.held.root_fd, self.stage_parts[:-1]) as parent:
            current = os.stat(self.stage_parts[-1], dir_fd=parent, follow_symlinks=False)
        guards._regular(current, directory=True)
        if identity(current) != self.stage_identity:
            raise BootstrapError('bootstrap_stage_changed')
        for path, expected in self.reused.items():
            check_entry(self.held.root_fd, path, expected)

    def create(self):
        self.held.require_held()
        os.mkdir(STAGING, mode=0o700, dir_fd=self.held.root_fd)
        self.stage_identity = identity(os.stat(STAGING, dir_fd=self.held.root_fd, follow_symlinks=False))
        self.fd = os.open(STAGING, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.held.root_fd)
        self.check()
        os.fsync(self.held.root_fd)

    def prepare(self, content, directories, root_created):
        for path in sorted(directories, key=lambda p: (p.count('/'), p)):
            parts = path.split('/')
            with directory(self.fd, parts[:-1]) as parent:
                self.check()
                os.mkdir(parts[-1], mode=0o755, dir_fd=parent)
                self.inventory[path] = metadata(os.stat(parts[-1], dir_fd=parent, follow_symlinks=False))
                os.fsync(parent)
        for path, raw in sorted(content.items()):
            self.write(path, raw)
        self.units = sorted(p for p in self.inventory if
            ('/' not in p and p not in self.reused) or
            (p.count('/') == 1 and p.split('/')[0] in self.reused))
        self.units.remove('specroad.json'); self.units.append('specroad.json')
        self.check()
        verify_tree(self.fd, self.inventory)
        journal = {'format': 'specroad-bootstrap-v1', 'state': 'prepared',
            'root_identity': identity(os.fstat(self.held.root_fd)), 'root_created': root_created,
            'stage_identity': self.stage_identity, 'units': self.units,
            'reused_directories': self.reused, 'entries': self.inventory}
        self.write('journal.json', canonical_json_bytes(journal))
        os.fsync(self.fd)

    def write(self, path, raw):
        parts = path.split('/')
        with directory(self.fd, parts[:-1]) as parent:
            self.check()
            fd = os.open(parts[-1], os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=parent)
            created = os.fstat(fd)
            try:
                offset = 0
                while offset < len(raw):
                    count = os.write(fd, raw[offset:])
                    if count <= 0: raise OSError(errno.EIO, 'Short bootstrap write')
                    offset += count
                os.fsync(fd)
            finally:
                # Retain the actual owned prefix even if a write/fsync fails.
                size = os.fstat(fd).st_size
                self.inventory[path] = metadata(created, raw[:size])
                os.close(fd)
            os.fsync(parent)

    def unit_locations(self):
        """Observe actual moves, including a failure after the native rename."""
        locations = {}
        for path in self.units:
            parts = path.split('/')
            with directory(self.fd, parts[:-1]) as staged, directory(self.held.root_fd, parts[:-1]) as target:
                a, b = info_at(staged, parts[-1]), info_at(target, parts[-1])
                if (a is None) == (b is None):
                    raise BootstrapError('bootstrap_unit_ambiguous', path=path)
                selected = staged if a is not None else target
                verify_unit(selected, parts[-1], self.inventory, path,
                            receipt_identity=self.stage_identity if self.stage_parts == COMPLETED else None)
                locations[path] = a is None
        return locations

    def checked_locations(self):
        self.check()
        locations = self.unit_locations()
        # An actual publication/rollback always has a complete ordered prefix.
        values = list(locations.values())
        if values != sorted(values, reverse=True):
            raise BootstrapError('bootstrap_publication_order_conflict')
        for path in self.reused:
            expected = {p.split('/')[1] for p, moved in locations.items()
                        if moved and p.startswith(path + '/')}
            with directory(self.held.root_fd, (path,)) as target:
                if set(os.listdir(target)) != expected:
                    raise BootstrapError('bootstrap_reused_directory_changed', path=path)
        remaining = {p: value for p, value in self.inventory.items() if not any(
            moved and (p == unit or p.startswith(unit + '/')) for unit, moved in locations.items())}
        verify_tree(self.fd, remaining)
        self.check()
        return locations

    def publish(self):
        for path in self.units:
            if self.checked_locations()[path]:
                continue
            parts = path.split('/')
            with directory(self.fd, parts[:-1]) as staged, directory(self.held.root_fd, parts[:-1]) as target:
                rename_new(self.function, staged, parts[-1], target, parts[-1])
        self.check()
        if not all(self.checked_locations().values()):
            raise BootstrapError('bootstrap_publication_incomplete')
        os.fsync(self.held.root_fd)
        self.committed = True

    def retain_completed(self):
        """Atomically retain the durable control record after full publication.

        The original record and empty reused-directory wrappers remain evidence;
        no unlink window can make a completed bootstrap an ownerless empty stage.
        """
        if not all(self.checked_locations().values()):
            raise BootstrapError('bootstrap_publication_incomplete')
        if self.stage_parts == COMPLETED:
            return
        with directory(self.held.root_fd, COMPLETED[:-1]) as parent:
            self.check()
            _rename_native(self.function, self.held.root_fd, STAGING, parent, COMPLETED[-1])
            self.stage_parts = COMPLETED
            os.fsync(parent)
            os.fsync(self.held.root_fd)
        self.checked_locations()

    def cleanup(self):
        self.check()
        moved = self.checked_locations() if self.units else {}
        if self.committed:
            self.retain_completed()
            return
        if not self.committed:
            for path, published in reversed(tuple(moved.items())):
                if published:
                    parts = path.split('/')
                    with directory(self.fd, parts[:-1]) as staged, directory(self.held.root_fd, parts[:-1]) as target:
                        self.check()
                        verify_unit(target, parts[-1], self.inventory, path)
                        rename_new(self.function, target, parts[-1], staged, parts[-1])
            moved = {}
        remaining = {p: v for p, v in self.inventory.items()
                     if not any(yes and (p == unit or p.startswith(unit + '/')) for unit, yes in moved.items())}
        verify_tree(self.fd, remaining)
        for path in sorted(remaining, key=lambda p: (p.count('/'), p), reverse=True):
            parts = path.split('/')
            with directory(self.fd, parts[:-1]) as parent:
                self.check()
                expected = remaining[path]; check_entry(parent, parts[-1], expected)
                if expected['kind'] == 'directory': os.rmdir(parts[-1], dir_fd=parent)
                else: os.unlink(parts[-1], dir_fd=parent)
                os.fsync(parent)
        self.check()
        os.rmdir(STAGING, dir_fd=self.held.root_fd)
        os.fsync(self.held.root_fd)

    def close(self):
        if self.fd is not None:
            os.close(self.fd); self.fd = None
