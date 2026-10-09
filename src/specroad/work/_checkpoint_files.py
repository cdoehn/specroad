"""Descriptor-bound reads for the private work store.

The caller supplies its existing logical error policy. These helpers only read
and recheck held descriptors; they neither publish generations nor touch project
journals. Exclusive creation and atomic replacement remain shared primitives.
"""

import os

from ..security import paths as guards
from ._root_lock import _private


def _directory(held, folder):
    return held._children[('checkpoints', 'objects', 'results').index(folder)]


def read_file(held, folder, name, *, check, error_type, sync=False, expected_size=None,
              maximum=None, bindings=None):
    held.check()
    parent = _directory(held, folder)
    logical = folder + '/' + name
    try:
        before = os.stat(name, dir_fd=parent, follow_symlinks=False)
        _private(before)
        check(expected_size is None or before.st_size == expected_size,
              'checkpoint_bytes_changed', path=logical)
        check(maximum is None or before.st_size <= maximum,
              'checkpoint_metadata_too_large', path=logical)
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            check(guards._signature(os.fstat(fd)) == guards._signature(before), path=logical)
            data = bytearray()
            while len(data) <= before.st_size:
                raw = os.read(fd, min(65536, before.st_size + 1 - len(data)))
                if not raw:
                    break
                data.extend(raw)
            if sync:
                os.fsync(fd)
                os.fsync(parent)
            now = os.stat(name, dir_fd=parent, follow_symlinks=False)
            _private(now)
            check(len(data) == before.st_size
                  and guards._signature(now) == guards._signature(before)
                  and guards._signature(os.fstat(fd)) == guards._signature(before), path=logical)
            held.check()
            if bindings is not None:
                key, signature = (folder, name), guards._signature(before)
                check(key not in bindings or bindings[key] == signature,
                      'checkpoint_bytes_changed', path=logical)
                bindings[key] = signature
            return bytes(data)
        finally:
            os.close(fd)
    except FileNotFoundError as error:
        raise error_type('checkpoint_bytes_missing', path=logical) from error


def verify_bindings(held, bindings, *, check, error_type):
    """Close the checked read set without silently trusting earlier path reads."""
    for (folder, name), signature in bindings.items():
        held.check()
        parent, logical = _directory(held, folder), folder + '/' + name
        try:
            before = os.stat(name, dir_fd=parent, follow_symlinks=False)
            _private(before)
            check(guards._signature(before) == signature, 'checkpoint_bytes_changed', path=logical)
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            try:
                check(guards._signature(os.fstat(fd)) == signature,
                      'checkpoint_bytes_changed', path=logical)
                now = os.stat(name, dir_fd=parent, follow_symlinks=False)
                _private(now)
                check(guards._signature(now) == signature, 'checkpoint_bytes_changed', path=logical)
            finally:
                os.close(fd)
        except FileNotFoundError as error:
            raise error_type('checkpoint_bytes_missing', path=logical) from error
    held.check()
