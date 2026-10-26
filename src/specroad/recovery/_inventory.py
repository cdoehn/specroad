"""Native complete raw-byte inventory; no locks, journal writes or Git reads."""
import os
import stat
from unicodedata import normalize

from ..changes._lock_files import LockFiles
from ..model.canonical import canonical_json_sha256
from ..security import ProjectBoundary
from ..security.resource_access import opened_resource, directory_entries
from ._codec import file_row, root_path, safe_path, namespace
from .values import require


def boundary(root):
    value = os.fspath(root)
    root_path(value)
    result = ProjectBoundary(root)
    require(str(result.root) == value, 'restore_canonical_root_required', exit_code=7)
    return result


def check_aliases(bound, path):
    """Inspect ancestor names through native descriptors, without taking a lock.

    Only names are listed at the project root; unrelated files and Git content
    are never opened. An absent canonical component must not hide an alias.
    """
    parts = safe_path(path).split('/')
    with LockFiles(bound.root) as access:
        require(access.boundary._root_identity == bound._root_identity,
                'restore_root_changed', exit_code=7)
        for index, part in enumerate(parts):
            with access.directory(parts[:index]) as parent:
                if parent is None:
                    break
                key = normalize('NFC', part).casefold()
                require(all(name == part or normalize('NFC', name).casefold() != key
                            for name in os.listdir(parent)),
                        'restore_portable_alias', path=path, exit_code=7)
    bound._check_root()


def observe(bound, roots):
    entries, files, pending = {}, {}, [(p, True) for p in reversed(roots)]
    while pending:
        path, optional = pending.pop()
        safe_path(path)
        check_aliases(bound, path)
        with opened_resource(bound, path, directory=None, missing_ok=optional) as (fd, info):
            if fd is None:
                entries[path] = {'path': path, 'kind': 'missing'}
            elif stat.S_ISDIR(info.st_mode):
                entries[path] = {'path': path, 'kind': 'directory'}
                children = directory_entries(bound, path)
                pending.extend((path + '/' + name, False) for name, _ in reversed(children))
            else:
                require(info.st_nlink == 1, 'restore_linked_file', path=path, exit_code=7)
                chunks = []
                while True:
                    chunk = os.read(fd, 65536)
                    if not chunk:
                        break
                    chunks.append(chunk)
                raw = b''.join(chunks)
                require(len(raw) == info.st_size, 'restore_inventory_changed', path=path, exit_code=6)
                files[path] = raw
                entries[path] = {**file_row(path, raw), 'kind': 'file'}
        check_aliases(bound, path)
    namespace(entries)
    result = {'roots': roots, 'entries': [entries[p] for p in sorted(entries, key=lambda p: p.encode('utf-8'))]}
    result['sha256'] = canonical_json_sha256(result)
    bound._check_root()
    return result, files


def read_source(bound, path):
    safe_path(path)
    check_aliases(bound, path)
    with opened_resource(bound, path) as (_, info):
        require(info.st_nlink == 1, 'restore_linked_file', path=path, exit_code=7)
        raw = bound.read_bytes(path)
    check_aliases(bound, path)
    return raw
