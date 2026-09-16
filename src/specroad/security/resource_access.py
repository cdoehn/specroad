"""Descriptor-relative enumeration and streaming under an existing boundary.

No pathname-only fallback. Only caller-owned descriptors are closed. The helpers
check observed changes, not an atomic multi-file transaction or OS sandbox.
"""

from contextlib import contextmanager
import errno
import os
import stat

from . import paths as guards
from .errors import SafetyViolation


@contextmanager
def opened_resource(boundary, path, *, directory=False):
    if not isinstance(boundary, guards.ProjectBoundary):
        raise TypeError("A ProjectBoundary is required")
    parts = guards._parts(path)
    if not guards._HAS_SAFE_OPEN:
        raise OSError(errno.ENOTSUP, "Secure project reads are unavailable")
    boundary._check_root()
    descriptors = []
    entries = []
    try:
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        parent = os.open(boundary.root, directory_flags)
        descriptors.append(parent)
        if guards._identity(os.fstat(parent)) != boundary._root_identity:
            raise SafetyViolation("Project root changed while opening")
        for index, name in enumerate(parts):
            is_directory = directory or index < len(parts) - 1
            before = os.stat(name, dir_fd=parent, follow_symlinks=False)
            guards._regular(before, directory=is_directory)
            flags = directory_flags if is_directory else os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0)
            descriptor = os.open(name, flags, dir_fd=parent)
            descriptors.append(descriptor)
            opened = os.fstat(descriptor)
            guards._regular(opened, directory=is_directory)
            if guards._identity(opened) != guards._identity(before):
                raise SafetyViolation("Project entry changed while opening")
            entries.append((parent, name, guards._identity(opened), is_directory))
            if is_directory:
                try:
                    os.stat("specroad.json", dir_fd=descriptor, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise SafetyViolation("Nested project roots cannot be combined")
                parent = descriptor
        initial = os.fstat(descriptors[-1])
        yield descriptors[-1], initial
        if guards._signature(os.fstat(descriptors[-1])) != guards._signature(initial):
            raise SafetyViolation("Resource changed during inspection")
        for parent, name, identity, is_directory in entries:
            current = os.stat(name, dir_fd=parent, follow_symlinks=False)
            guards._regular(current, directory=is_directory)
            if guards._identity(current) != identity:
                raise SafetyViolation("Resource path changed during inspection")
        boundary._check_root()
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            raise SafetyViolation("Project path is not safely traversable") from error
        raise
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def directory_entries(boundary, path, *, missing_ok=False):
    """Stable names/types only, with fresh non-following stat for each entry."""
    entered = False
    try:
        with opened_resource(boundary, path, directory=True) as (descriptor, initial):
            entered = True
            names = sorted(os.listdir(descriptor))
            result = []
            for name in names:
                guards._parts(name)
                metadata = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                is_directory = stat.S_ISDIR(metadata.st_mode)
                guards._regular(metadata, directory=is_directory)
                result.append((name, is_directory))
            if names != sorted(os.listdir(descriptor)):
                raise SafetyViolation("Directory membership changed during inspection")
        return tuple(result)
    except FileNotFoundError:
        if entered or not missing_ok:
            raise
        return None
