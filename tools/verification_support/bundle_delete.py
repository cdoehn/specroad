"""Bounded regular-file deletion; frozen into each Apply entrypoint."""
from hashlib import sha256
import os
from pathlib import Path
import stat


def delete_bound_file(root, name, digest, *, absent=False, remove=True):
    """Unlink one bound regular inode through held no-follow directory descriptors.

    Runs under the native Apply ownership lock. Never removes directories and
    never treats an unexpected missing file as permission for deletion.
    """
    parts = Path(name).parts
    if (not parts or str(Path(name)) != name or Path(name).is_absolute()
            or any(p.lower() in ('.', '..', '.git', '.patchharbor') for p in parts)):
        raise ValueError('Unsafe deletion path')
    directories = []
    descriptor = None
    try:
        directories.append(os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW))
        for part in parts[:-1]:
            directories.append(os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                       dir_fd=directories[-1]))
        parent = directories[-1]
        try:
            info = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            if absent:
                for length, directory in enumerate(directories):
                    current = Path(root).joinpath(*parts[:length]).lstat()
                    held = os.fstat(directory)
                    if (current.st_dev, current.st_ino) != (held.st_dev, held.st_ino):
                        raise ValueError('Deleted path parent changed: ' + name)
                return
            raise ValueError('Bound deletion preimage is missing: ' + name) from None
        if absent:
            raise ValueError('Deleted file reappeared: ' + name)
        if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o644
                or info.st_nlink != 1 or info.st_size > 32 * 1024 * 1024):
            raise ValueError('Deletion requires a single-link regular 0644 file: ' + name)
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        attributes = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        signature = tuple(getattr(info, field) for field in attributes)
        if tuple(getattr(os.fstat(descriptor), field) for field in attributes) != signature:
            raise ValueError('Deletion preimage replaced during open: ' + name)
        hashed = sha256()
        read_size = 0
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            read_size += len(block)
            if read_size > info.st_size:
                raise ValueError('Deletion preimage grew during read: ' + name)
            hashed.update(block)
        current = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
        if (hashed.hexdigest() != digest
                or tuple(getattr(current, field) for field in attributes) != signature
                or tuple(getattr(os.fstat(descriptor), field) for field in attributes) != signature):
            raise ValueError('Deletion preimage changed during read: ' + name)
        # Ensure held parents still name this root/path before unlinking.
        for length, directory in enumerate(directories):
            current = (Path(root).joinpath(*parts[:length])).lstat()
            held = os.fstat(directory)
            if (current.st_dev, current.st_ino) != (held.st_dev, held.st_ino):
                raise ValueError('Deletion parent changed: ' + name)
        if remove:
            os.unlink(parts[-1], dir_fd=parent)
            os.fsync(parent)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        for directory in reversed(directories):
            os.close(directory)
