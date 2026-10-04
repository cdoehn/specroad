"""Shared bookkeeping for possible operational writes and recovery failures."""
from .recovery_values import RecoveryError

_ERROR_PATH = object()


class RecoveryMutation:
    """Mark the same write boundary locally and in an enclosing recovery call."""

    def __init__(self, before_create=None):
        self.possible = False
        self._before_create = before_create

    def start(self):
        self.possible = True
        if self._before_create is not None:
            self._before_create()


def recovery_failure(error, *, reason, mutation_possible, path=_ERROR_PATH):
    """Translate metadata while the caller retains its mutation and path policy."""
    return RecoveryError(
        getattr(error, 'reason', reason),
        path=getattr(error, 'path', None) if path is _ERROR_PATH else path,
        exit_code=getattr(error, 'exit_code', 5),
        mutation_possible=mutation_possible,
    )
