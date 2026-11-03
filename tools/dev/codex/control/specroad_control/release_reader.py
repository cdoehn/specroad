"""Read installed code through private directory descriptors; never write it.

Operational-data helpers deliberately reject the running code directory.
Self-verification therefore uses this separate, bounded read-only boundary.
"""
import os
from pathlib import Path, PurePosixPath
import stat

from .errors import ControlError
from .local import outside


def reject():
    raise ControlError('release_unproven', 'The installed Control release is incomplete or unsafe.')


def directory(fd):
    info = os.fstat(fd)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        reject()


def read_tree(fd, tree, prefix, result):
    directory(fd)
    if set(os.listdir(fd)) != set(tree):
        reject()
    for name, children in tree.items():
        flags = os.O_RDONLY | os.O_NOFOLLOW | (os.O_DIRECTORY if children is not None else os.O_NONBLOCK)
        child = os.open(name, flags, dir_fd=fd)
        try:
            before = os.fstat(child)
            if children is not None:
                read_tree(child, children, prefix + name + '/', result)
            else:
                if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
                        or before.st_mode & 0o077 or before.st_nlink != 1 or before.st_size > 65536):
                    reject()
                with os.fdopen(child, 'rb', closefd=False) as stream:
                    raw = stream.read(65537)
                if len(raw) > 65536:
                    reject()
                result[prefix + name] = raw
            after = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if (before.st_dev, before.st_ino, before.st_mode, before.st_uid, before.st_nlink,
                    before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_mode,
                    after.st_uid, after.st_nlink, after.st_size, after.st_mtime_ns):
                reject()
        finally:
            os.close(child)
    if set(os.listdir(fd)) != set(tree):
        reject()


def release_bytes(root, names):
    """Read exactly a receipt's safe file inventory below an external release root."""
    root = Path(root)
    parent = outside(root.parent)
    if not 0 < len(names) <= 1024:
        reject()
    tree = {}
    for name in names:
        if not isinstance(name, str):
            reject()
        path = PurePosixPath(name)
        if (path.is_absolute() or str(path) != name or not path.parts or len(path.parts) > 8
                or any(p in ('.', '..', '.git') for p in path.parts) or '\x00' in name or '\\' in name):
            reject()
        node = tree
        for part in path.parts[:-1]:
            node = node.setdefault(part, {})
            if node is None:
                reject()
        if path.name in node:
            reject()
        node[path.name] = None
    # The parent is operational storage, so the existing Git/symlink guard
    # applies. Only descriptor-relative reads may enter the code directory.
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        directory(parent_fd)
        fd = os.open(root.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        try:
            before = os.fstat(fd)
            result = {}
            read_tree(fd, tree, '', result)
            after = os.stat(root.name, dir_fd=parent_fd, follow_symlinks=False)
            if (before.st_dev, before.st_ino, before.st_mode, before.st_uid) != (after.st_dev,
                    after.st_ino, after.st_mode, after.st_uid):
                reject()
            return result
        finally:
            os.close(fd)
    finally:
        os.close(parent_fd)
