"""Current compatible build for all native Work adapters; no Restore import."""
from ..qualification.errors import RestoreError
from .resume import _runtime_build, WorkResumeError


def _build():
    try:
        return _runtime_build()
    except WorkResumeError as error:
        raise RestoreError(error.reason, exit_code=error.exit_code) from error
