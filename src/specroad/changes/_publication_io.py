"""Shared descriptor-relative atomic image replacement for publish and recovery.

Callers retain policy decisions, lock/authority checks and error vocabulary.  This
module owns only the byte-bound final move: revalidate the source image, keep its
opened identity stable, optionally set the final mode durably, execute caller
checks immediately before replace, fsync both directories, and verify the final
image by the same identity and content binding.
"""
from collections.abc import Callable
import os

from ..security import paths as guards
from ._staging_files import _image


def replace_bound_image(source_dir, source_name, target_dir, target_name, *,
                        size, digest, identity, mode=None,
                        source_changed: Callable[[], Exception],
                        before_open=None, before_mutation=None,
                        before_replace=None, after_replace=None):
    """Atomically move one exact regular image between already-bound directories.

    ``mode=None`` preserves the source mode.  Policy checks and caller state
    transitions are callbacks so publication and recovery keep their existing
    semantics while sharing the filesystem mutation primitive.
    """
    _image(source_dir, source_name, size, digest, identity=identity)
    if before_open is not None:
        before_open()
    fd = os.open(source_name,
                 os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0),
                 dir_fd=source_dir)
    try:
        if guards._identity(os.fstat(fd)) != identity:
            raise source_changed()
        if before_mutation is not None:
            before_mutation()
        if mode is not None:
            os.fchmod(fd, mode)
            os.fsync(fd)
        info = os.fstat(fd)
        if before_replace is not None:
            before_replace()
        os.replace(source_name, target_name,
                   src_dir_fd=source_dir, dst_dir_fd=target_dir)
        if after_replace is not None:
            after_replace(info)
        os.fsync(target_dir)
        os.fsync(source_dir)
        _image(target_dir, target_name, size, digest, identity=identity)
        return info
    finally:
        os.close(fd)
