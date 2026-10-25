"""Shared destination identity and owned-root rollback for bootstrap commands.

Command-specific content, target policy and journal recovery remain with the
caller. These primitives only manage the same root lifecycle used by init.
"""
import os
from pathlib import Path
import sys

from ..changes._lock_files import LockFiles
from ..changes.lock_values import ProjectLockError
from ..security import SafetyViolation
from ..security import paths as guards
from ._bootstrap_io import BootstrapError, STAGING, directory, identity, info_at


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
        self.current = info_at(parent_held.root_fd, target.name)
        if self.current is not None:
            guards._regular(self.current, directory=True)
        self.created = False
        self.created_identity = None

    def create(self):
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

    def rollback(self, tree, original):
        """Remove only a proven owned, empty root after successful tree rollback."""
        rollback_complete = False
        if tree is not None and tree.fd is not None:
            try:
                tree.cleanup()
                rollback_complete = not tree.committed
            except (BootstrapError, ProjectLockError, SafetyViolation, OSError):
                raise BootstrapError('bootstrap_recovery_required', path=STAGING,
                                     mutation_possible=True) from original
        elif tree is None:
            rollback_complete = True
        if self.created and rollback_complete:
            self.parent_held.require_held()
            now = info_at(self.parent_held.root_fd, self.target.name)
            if now is not None and identity(now) == self.created_identity:
                with directory(self.parent_held.root_fd, (self.target.name,)) as fd:
                    if os.listdir(fd):
                        raise BootstrapError('bootstrap_root_not_empty', mutation_possible=True) from original
                os.rmdir(self.target.name, dir_fd=self.parent_held.root_fd)
                os.fsync(self.parent_held.root_fd)
