"""Shared destination identity and guarded lifecycle for bootstrap commands.

Command-specific content, target policy and passive completion remain with the
caller. These primitives only manage the same root lifecycle used by init.
"""
import os
from pathlib import Path
import sys

from ..changes._lock_files import LockFiles
from ..security import paths as guards
from ._bootstrap_io import BootstrapError, identity, info_at


def root_destination(path, *, cwd=None, invalid_reason):
    if not isinstance(path, (str, Path)) or not str(path) or '\0' in str(path):
        raise BootstrapError(invalid_reason, exit_code=2)
    if not sys.platform.startswith('linux') or not guards._HAS_SAFE_OPEN:
        raise BootstrapError('bootstrap_platform_unavailable', exit_code=5)
    requested = Path(path)
    if not requested.is_absolute():
        requested = (Path.cwd() if cwd is None else Path(cwd)) / requested
    # Normalize lexical dots without resolving the target itself through a link.
    requested = Path(os.path.abspath(requested))
    if requested == requested.parent:
        raise BootstrapError('bootstrap_root_destination_invalid', exit_code=2)
    parent = requested.parent.resolve(strict=True)
    return parent, parent / requested.name


class BootstrapRoot:
    def __init__(self, parent_held, target):
        self.parent_held = parent_held
        self.target = target
        from .bootstrap_guard import names
        for name in names(target):
            if info_at(parent_held.root_fd, name) is not None:
                raise BootstrapError('project_corrupted', exit_code=5, path=name)
        self.protection = None
        self.current = info_at(parent_held.root_fd, target.name)
        if self.current is not None:
            guards._regular(self.current, directory=True)
        self.created = False
        self.created_identity = None

    def protect(self, command, content, directories, *, input_binding):
        from .bootstrap_guard import BootstrapGuard
        self.protection = BootstrapGuard(self.parent_held, self.target, command,
            content, directories, input_binding=input_binding)
        self.protection.start()

    def complete(self, verify):
        if self.protection is None:
            raise BootstrapError('bootstrap_protection_required', exit_code=7)
        self.protection.finish(verify)

    def close(self):
        if self.protection is not None:
            self.protection.close()

    def create(self):
        if self.protection is None or not self.protection.started:
            raise BootstrapError('bootstrap_protection_required', exit_code=7)
        self.protection.check()
        os.mkdir(self.target.name, mode=0o755, dir_fd=self.parent_held.root_fd)
        self.created = True
        self.created_identity = identity(os.stat(
            self.target.name, dir_fd=self.parent_held.root_fd, follow_symlinks=False))
        os.fsync(self.parent_held.root_fd)

    def acquire(self, stack):
        held = stack.enter_context(LockFiles(self.target))
        held.acquire()
        expected = self.created_identity if self.created else identity(self.current)
        if identity(os.fstat(held.root_fd)) != expected:
            raise BootstrapError('bootstrap_root_changed')
        return held
