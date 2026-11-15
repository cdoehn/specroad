"""Current compatible build for all native Work adapters; no Restore import."""
from ..qualification.errors import QualificationError
from .resume import _runtime_build, WorkResumeError


def _build():
    try:
        return _runtime_build()
    except WorkResumeError as error:
        raise QualificationError(error.reason, exit_code=error.exit_code) from error
