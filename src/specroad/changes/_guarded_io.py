"""Descriptor-relative reads shared by the writer and completion observer."""
from ._journal_io import _read
from .write_guard_values import WriteGuardError


def _read_path(files,path,*,optional=False):
    with files.directory(tuple(path.split('/')[:-1])) as fd:
        if fd is None:
            if optional:return None
            raise WriteGuardError('write_resource_missing')
        try:return _read(fd,path.rsplit('/',1)[-1])
        except FileNotFoundError:
            if optional:return None
            raise
