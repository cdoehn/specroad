"""Private, inode-bound immutable handoff records under the held Work mutex."""
import os

from ..changes._staging_files import _write_new
from ..recovery.values import require
from ..security import paths as guards
from ._root_lock import _private


class HandoffFiles:
    name = 'restore-owner-handoffs'

    def __init__(self, held):
        self.held = held
        self.parent = held._children[0]
        self.fd = None
        self.seen = {}
        try:
            info = os.stat(self.name, dir_fd=self.parent, follow_symlinks=False)
        except FileNotFoundError:
            return
        _private(info, directory=True)
        self.fd = held._directory(self.parent, self.name)

    def read(self, name, *, sync=False):
        self.held.check()
        _private(os.fstat(self.fd), directory=True)
        before = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
        _private(before)
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.fd)
        try:
            signature = guards._signature(before)
            require(guards._signature(os.fstat(fd)) == signature,
                    'restore_work_handoff_changed', exit_code=6)
            chunks = bytearray()
            while len(chunks) <= before.st_size:
                part = os.read(fd, min(65536, before.st_size + 1 - len(chunks)))
                if not part:
                    break
                chunks.extend(part)
            if sync:
                os.fsync(fd)
                os.fsync(self.fd)
            now = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
            _private(now)
            require(len(chunks) == before.st_size
                    and guards._signature(now) == signature
                    and guards._signature(os.fstat(fd)) == signature,
                    'restore_work_handoff_changed', exit_code=6)
            self.held.check()
            return bytes(chunks), guards._identity(now)
        finally:
            os.close(fd)

    def load(self):
        names = [] if self.fd is None else sorted(os.listdir(self.fd))
        for name in names:
            guards._parts(name)
            self.seen[name] = self.read(name)
        self.check()
        return {name: pair[0] for name, pair in self.seen.items()}

    def check(self):
        self.held.check()
        if self.fd is None:
            try:
                os.stat(self.name, dir_fd=self.parent, follow_symlinks=False)
            except FileNotFoundError:
                return
            require(False, 'restore_work_handoff_namespace_changed', exit_code=6)
        require(set(os.listdir(self.fd)) == set(self.seen),
                'restore_work_handoff_namespace_changed', exit_code=6)
        for name, pair in self.seen.items():
            require(self.read(name) == pair, 'restore_work_handoff_changed', exit_code=6)

    def write(self, name, raw):
        self.check()
        if self.fd is None:
            os.mkdir(self.name, 0o700, dir_fd=self.parent)
            os.fsync(self.parent)
            self.fd = self.held._directory(self.parent, self.name)
            _private(os.fstat(self.fd), directory=True)
        if name not in self.seen:
            identity = _write_new(self.fd, name, raw)
            self.seen[name] = (raw, identity)
        require(self.read(name, sync=True) == self.seen[name] and self.seen[name][0] == raw,
                'restore_work_handoff_changed', exit_code=6)
        self.check()
