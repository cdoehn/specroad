"""Descriptor-bound reads through exactly one canonical project root."""

from dataclasses import dataclass
import errno
import os
from pathlib import Path
import stat

from .errors import SafetyViolation


_HAS_SAFE_OPEN = (os.name == "posix" and os.open in os.supports_dir_fd
                  and os.stat in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW")
                  and hasattr(os, "O_DIRECTORY"))


def _parts(logical_path):
    if not isinstance(logical_path, str) or not logical_path or "\\" in logical_path:
        raise SafetyViolation("A relative project path is required")
    try:
        logical_path.encode("utf-8")
    except UnicodeError as error:
        raise SafetyViolation("Project path is not valid Unicode") from error
    parts = logical_path.split("/")
    if any(not part or part in {".", ".."} or ":" in part
           or any(ord(char) < 32 or ord(char) == 127 for char in part) for part in parts):
        raise SafetyViolation("Unsafe project path")
    return tuple(parts)


def _identity(info):
    return info.st_dev, info.st_ino


def _signature(info):
    return (_identity(info), info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _regular(info, *, directory=False):
    reparse = getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if stat.S_ISLNK(info.st_mode) or reparse:
        raise SafetyViolation("Linked project paths are not accepted")
    wanted = stat.S_ISDIR if directory else stat.S_ISREG
    if not wanted(info.st_mode):
        raise SafetyViolation("Special project entries are not accepted")


@dataclass(frozen=True, init=False)
class ProjectBoundary:
    """Read capability for exactly one existing canonical root; never a root list.

    Links are conservatively rejected, including internal links. No project bytes
    are read through a path-only check followed by an unguarded open. Platforms
    without descriptor-relative non-following opens fail closed.
    """
    root: Path
    _root_identity: tuple

    def __init__(self, root):
        if not isinstance(root, (str, Path)):
            raise SafetyViolation("Exactly one project root is required")
        canonical = Path(root).resolve(strict=True)
        info = canonical.lstat()
        _regular(info, directory=True)
        object.__setattr__(self, "root", canonical)
        object.__setattr__(self, "_root_identity", _identity(info))

    def _check_root(self):
        info = self.root.lstat()
        _regular(info, directory=True)
        if _identity(info) != self._root_identity:
            raise SafetyViolation("Project root changed during use")

    def read_bytes(self, logical_path):
        parts = _parts(logical_path)
        if not _HAS_SAFE_OPEN:
            raise OSError(errno.ENOTSUP, "Secure project reads are unavailable")
        self._check_root()
        descriptors = []
        entries = []
        try:
            directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            parent = os.open(self.root, directory_flags)
            descriptors.append(parent)
            if _identity(os.fstat(parent)) != self._root_identity:
                raise SafetyViolation("Project root changed while opening")
            for index, name in enumerate(parts):
                directory = index < len(parts) - 1
                before = os.stat(name, dir_fd=parent, follow_symlinks=False)
                _regular(before, directory=directory)
                flags = directory_flags if directory else os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0)
                opened_fd = os.open(name, flags, dir_fd=parent)
                descriptors.append(opened_fd)
                opened = os.fstat(opened_fd)
                _regular(opened, directory=directory)
                if _identity(before) != _identity(opened):
                    raise SafetyViolation("Project entry changed while opening")
                entries.append((parent, name, _identity(opened)))
                if directory:
                    # A nested project is not part of this root's canonical model.
                    try:
                        os.stat("specroad.json", dir_fd=opened_fd, follow_symlinks=False)
                    except FileNotFoundError:
                        pass
                    else:
                        raise SafetyViolation("Nested project roots cannot be combined")
                    parent = opened_fd
            file_descriptor = descriptors[-1]
            stream = os.fdopen(file_descriptor, "rb")
            descriptors.pop()  # fdopen owns it only after successful construction.
            with stream:
                initial_content = os.fstat(stream.fileno())
                data = stream.read()
                if (_signature(os.fstat(stream.fileno())) != _signature(initial_content)
                        or len(data) != initial_content.st_size):
                    raise SafetyViolation("Project content changed during the read")
            for index, (parent_fd, name, expected) in enumerate(entries):
                current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                _regular(current, directory=index < len(entries) - 1)
                if _identity(current) != expected:
                    raise SafetyViolation("Project entry changed while reading")
            self._check_root()
            return data
        except OSError as error:
            if error.errno in (errno.ELOOP, errno.ENOTDIR):
                raise SafetyViolation("Project path is not safely traversable") from error
            raise
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)


