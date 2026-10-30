"""Preserve native Work error classes at the public Restore boundary."""
from functools import wraps

from ..recovery.values import RestoreError
from ..storage.archive import ArchiveError
from .checkpoints import CheckpointStorageError
from .resume import WorkResumeError
from ._data_contract import WorkManifestError


def work_errors(function):
    @wraps(function)
    def call(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except RestoreError:
            raise
        except (WorkResumeError, ArchiveError) as error:
            raise RestoreError(error.reason, exit_code=error.exit_code) from error
        except CheckpointStorageError as error:
            raise RestoreError(error.reason, path=error.path,
                exit_code=5 if error.reason == 'checkpoint_bytes_missing' else 6) from error
        except WorkManifestError as error:
            raise RestoreError('work_manifest_invalid') from error
    return call
