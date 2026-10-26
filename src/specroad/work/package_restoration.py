"""Restore only the actually retained, explicitly hash-bound Work file.

This host adapter discovers no backups and consumes no saved export report or
prompt as checkpoint data. It preserves the existing read-only package and
durable restore contracts, including real prefix state on interrupted writes.
"""
from ..security import ProjectBoundary, SafetyViolation
from ..storage.archive import ArchiveError, _hash
from .packages import restore_work_package
from .root import _path


def restore_work_package_file(filename, *, expected_sha256, registry, protected_roots, directory):
    """Read one explicit canonical absolute file and restore its checked bytes.

    All package bytes are verified before allocation; the source is rechecked
    before and after each published generation. Original local Work/project
    paths are not consulted. The source directory is an additional protected
    input boundary, never an implicit destination or a normative write target.
    """
    _hash(expected_sha256)
    if (type(protected_roots) is not tuple or not protected_roots
            or any(type(root) is not ProjectBoundary for root in protected_roots)):
        raise ValueError('Explicit protected project/input/output boundaries are required')
    path = _path(filename)
    if path.parent.resolve(strict=True) != path.parent:
        raise SafetyViolation('A canonical Work package location is required')
    boundary = ProjectBoundary(path.parent)
    raw = boundary.read_bytes(path.name)

    def recheck():
        if path.parent.resolve(strict=True) != path.parent:
            raise SafetyViolation('Work package location changed')
        if boundary.read_bytes(path.name) != raw:
            raise ArchiveError('work_package_input_changed', exit_code=6)

    return restore_work_package(raw, expected_sha256=expected_sha256, registry=registry,
        protected_roots=(*protected_roots, boundary), directory=directory, _recheck_input=recheck)
