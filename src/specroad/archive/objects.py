"""Immutable snapshot objects and an explicitly external preparation store.

This store publishes complete inert files in an owned external directory. It
cannot publish into a protected project, create a Baseline, grant approval or
replace the normative writer's plan, lock, journal and receipt protocol. The
later Baseline writer consumes these exact bytes and content-addressed paths.
Whole-byte object values are intentional; this is no streaming manifest builder.
"""
from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import re
import secrets

from ..changes._lock_files import LockFiles
from ..changes._staging_files import _image, _write_new
from ..model.canonical import canonical_object_bytes
from ..model.errors import ModelError
from ..security import ProjectBoundary, SafetyViolation
from ..security import paths as guards
from ..security.resource_access import opened_resource


@dataclass(frozen=True)
class ObjectReference:
    sha256: str
    size: int

    def __post_init__(self):
        if type(self.sha256) is not str or re.fullmatch('[0-9a-f]{64}', self.sha256) is None:
            raise ModelError('snapshot_object_hash_required')
        if type(self.size) is not int or self.size < 0:
            raise ModelError('snapshot_object_size_required')

    @property
    def path(self):
        return 'archive/objects/' + self.sha256[:2] + '/' + self.sha256

    @property
    def data(self):
        return {'path': self.path, 'sha256': self.sha256, 'size': self.size}


@dataclass(frozen=True)
class SnapshotObject:
    """Exact content; logical role, media type and source identity belong to the manifest."""
    content: bytes

    def __post_init__(self):
        if type(self.content) is not bytes:
            raise ModelError('snapshot_object_bytes_required')

    @classmethod
    def from_json(cls, raw):
        return cls(canonical_object_bytes(raw))

    @classmethod
    def from_attachment(cls, raw):
        return cls(raw)

    @property
    def reference(self):
        return ObjectReference(sha256(self.content).hexdigest(), len(self.content))


def _reference(value):
    if type(value) is not ObjectReference:
        raise ModelError('snapshot_object_reference_required')
    return ObjectReference(value.sha256, value.size)


def read_snapshot_object(boundary, reference):
    """Verify an existing archived object without writes or Baseline-validity claims."""
    if type(boundary) is not ProjectBoundary:
        raise ModelError('snapshot_object_boundary_required')
    reference = _reference(reference)
    with opened_resource(boundary, reference.path) as (fd, initial):
        if initial.st_nlink != 1:
            raise SafetyViolation('Snapshot objects cannot be hardlinked')
        if initial.st_size != reference.size:
            raise ModelError('snapshot_object_size_mismatch', path=reference.path)
        content = bytearray()
        while len(content) <= reference.size:
            block = os.read(fd, min(65536, reference.size + 1 - len(content)))
            if not block:
                break
            content.extend(block)
        if len(content) != reference.size:
            raise ModelError('snapshot_object_size_mismatch', path=reference.path)
        if sha256(content).hexdigest() != reference.sha256:
            raise ModelError('snapshot_object_hash_mismatch', path=reference.path)
    return bytes(content)


class SnapshotObjectStore:
    """Prepare/reuse immutable objects outside every protected input/output root.

    The root must already exist, be private and belong to this process's user.
    The caller must supply every protected project/input/output boundary. No
    directories or files are created by construction or reads. Native local
    Linux locking is required for puts; unsupported storage fails closed.
    """

    def __init__(self, root, *, protected_roots):
        if (type(protected_roots) is not tuple or not protected_roots
                or any(type(item) is not ProjectBoundary for item in protected_roots)):
            raise ModelError('snapshot_protected_roots_required')
        path = Path(root)
        if not path.is_absolute() or path.resolve(strict=True) != path:
            raise SafetyViolation('An existing canonical external store root is required')
        self._boundary = ProjectBoundary(path)
        self._protected = tuple(protected_roots)
        self._check()

    @property
    def root(self):
        return self._boundary.root

    def _check(self):
        self._boundary._check_root()
        info = self.root.lstat()
        if info.st_mode & 0o077 or not hasattr(os, 'getuid') or info.st_uid != os.getuid():
            raise SafetyViolation('Snapshot preparation storage must be private and owned')
        for boundary in self._protected:
            boundary._check_root()
            if self.root.is_relative_to(boundary.root) or boundary.root.is_relative_to(self.root):
                raise SafetyViolation('Snapshot preparation and protected paths overlap')
        for parent in (self.root, *self.root.parents):
            try:
                (parent / 'specroad.json').lstat()
            except FileNotFoundError:
                continue
            raise SafetyViolation('Snapshot preparation storage cannot be inside a SpecRoad project')

    def get(self, reference):
        self._check()
        content = read_snapshot_object(self._boundary, reference)
        self._check()
        return content

    def put(self, value):
        if type(value) is not SnapshotObject:
            raise ModelError('snapshot_object_required')
        value = SnapshotObject(value.content)
        reference = value.reference
        self._check()
        with LockFiles(self.root) as files:
            if files.boundary._root_identity != self._boundary._root_identity:
                raise SafetyViolation('Snapshot preparation root changed')
            files.acquire()
            self._check()
            with files.directory(tuple(reference.path.split('/')[:-1]), create=True) as directory:
                try:
                    os.stat(reference.sha256, dir_fd=directory, follow_symlinks=False)
                except FileNotFoundError:
                    temporary = '.snapshot-' + secrets.token_hex(16)
                    identity = _write_new(directory, temporary, value.content)
                    files.require_held(); self._check()
                    # An atomic no-replace link exposes only fully written bytes.
                    # Any failure retains owned temporary data for inspection.
                    os.link(temporary, reference.sha256, src_dir_fd=directory,
                            dst_dir_fd=directory, follow_symlinks=False)
                    os.fsync(directory)
                    if guards._identity(os.stat(temporary, dir_fd=directory,
                                                follow_symlinks=False)) != identity:
                        raise SafetyViolation('Snapshot preparation image changed')
                    os.unlink(temporary, dir_fd=directory)
                    os.fsync(directory)
                    _image(directory, reference.sha256, reference.size, reference.sha256,
                           identity=identity)
                # Never replace an existing path, including corrupted contents.
                if self.get(reference) != value.content:
                    raise ModelError('snapshot_object_content_collision', path=reference.path)
                files.require_held(); self._check()
        return reference
