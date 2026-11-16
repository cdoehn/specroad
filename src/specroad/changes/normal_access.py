"""Normal project access observes interruption state; it never repairs it.

Only a live native writer capability can read its own unchanged inputs and
completion records. A matching PID or a serialized owner is not that capability.
"""
from contextlib import contextmanager
from contextvars import ContextVar

from .write_guard_values import WriteGuardError

_writer = ContextVar('specroad_native_writer', default=None)
_reader = ContextVar('specroad_native_read_mutex', default=None)


@contextmanager
def normal_read_mutex(files):
    """Reuse an actual held root mutex for read-only Work cancellation checks."""
    from ._lock_files import LockFiles
    if type(files) is not LockFiles:
        raise TypeError('An actual native root mutex is required')
    files.require_held()
    token = _reader.set(files)
    try:
        yield
        files.require_held()
    finally:
        _reader.reset(token)


class NormalAccessError(WriteGuardError):
    def __init__(self, observation):
        self.observation = dict(observation)
        super().__init__('project_' + observation['state'],
                         exit_code=6 if observation['state'] == 'writer_active' else 5)

    def diagnostic(self):
        return {**super().diagnostic(), **self.observation,
                'normal_operation_started': False, 'recovery_performed': False}


def require_normal_access(root, *, expected_project_id=None):
    from .locking import HeldProjectLock
    from ..security import ProjectBoundary
    held = _writer.get()
    boundary = ProjectBoundary(root)
    if type(held) is HeldProjectLock and held._files.boundary.root == boundary.root:
        held.check()
        if (held.record.data['kind'] == 'writer'
                and held._files.boundary._root_identity == boundary._root_identity
                and (expected_project_id is None or held.record.data['project_id'] == expected_project_id)
                and not held._files.journal_entries()
                and getattr(held, '_write_release_allowed', True)):
            return
    from ..storage.operational_preflight import observe_operational_preflight
    observed = observe_operational_preflight(boundary)
    observation = observe_normal_state(root, observed, expected_project_id=expected_project_id)
    if observation['state'] != 'clean':
        raise NormalAccessError(observation)


def observe_normal_state(root, observed, *, expected_project_id=None):
    """Do not defeat the bounded metadata scan with an unbounded diagnosis."""
    from .write_guard_read import inspect_write_state
    if not observed['inspection_complete']:
        state = 'corrupted' if (observed['unresolved_paths'] or any(
            p.startswith('.specroad/write-state/') for p in observed['unknown_paths'])) else 'unknown'
        return dict(state=state, project_corrupted=state == 'corrupted',
                    manual_git_restore_required=state == 'corrupted',
                    normal_operation_started=False, write_authorized=False,
                    recovery_performed=False, observation_only=True)
    result = inspect_write_state(root, expected_project_id=expected_project_id,
                                 _held_files=_reader.get())
    if result['state'] == 'writer_active':
        result['exit_code'] = 6
    if result['state'] == 'clean' and observed['consistency_state'] != 'consistent':
        # An unclassified entry cannot be made harmless by a narrower reader.
        result.update(state='unknown', exit_code=5)
    return result
