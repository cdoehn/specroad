"""Read private control files without creating or changing them."""
import json
import os
import stat

from dev.test_hosts.config import unique


def inspect_directory(root):
    for part in (root, *root.parents):
        if not stat.S_ISDIR(part.lstat().st_mode):
            raise ValueError('Linked or special control directory')
    info = root.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Control directory must be private')


def inspect_file(info):
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Control files must be private single regular files')


def read_json(path, *, max_bytes=1_000_000):
    inspect_directory(path.parent)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        inspect_file(before)
        if before.st_size > max_bytes:
            raise ValueError('Oversized live control file')
        with os.fdopen(os.dup(fd), 'rb') as stream:
            data = stream.read(max_bytes + 1)
        # An atomic replacement may publish a newer valid command meanwhile.
        # Read this complete descriptor generation; reject in-place mutation.
        after = os.fstat(fd)
        identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
        if identity(before) != identity(after) or len(data) != before.st_size:
            raise ValueError('Live control file changed while reading')
        return json.loads(data, object_pairs_hook=unique)
    finally:
        os.close(fd)
