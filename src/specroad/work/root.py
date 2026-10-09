"""Lazy external work location; native lease lifetime lives in _root_lock."""

from contextlib import contextmanager
import os
from pathlib import Path
import secrets
import sys

# Preserve the existing application-owned owner-probe seam as the same class.
from ..changes._lock_process import LinuxOwnerProbe
from ..security import ProjectBoundary, SafetyViolation
from ..security import paths as guards
from .manifest import WorkManifest
from ._root_lock import _HeldWorkRoot, _private, _DIRECTORIES, _BINDING, _LOCK


def _path(value):
    raw = os.fspath(value)
    if type(raw) is not str or not raw.startswith('/') or raw.startswith('//'):
        raise SafetyViolation('An absolute external work path is required')
    guards._parts(raw[1:])
    return Path(raw)


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
        self._allocated_identity = None

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
            self._allocated_identity = guards._identity(os.fstat(held._root))
            yield held

    @contextmanager
    def inspect_checkpoint(self):
        """Read existing data under the native mutex, preserving every owner file.

        This is no recovery, continuation approval or permission to publish.
        An active native owner still blocks. No absent storage is created.
        """
        if not sys.platform.startswith('linux') or not guards._HAS_SAFE_OPEN:
            raise SafetyViolation('Native work locking is unavailable')
        path = self._path or self._requested
        if path is None:
            raise SafetyViolation('No existing work location was supplied')
        self._outside(path)
        with _HeldWorkRoot(self, path, exclusive=False, inspection=True) as held:
            self._path = path
            self._allocated_identity = guards._identity(os.fstat(held._root))
            yield held
