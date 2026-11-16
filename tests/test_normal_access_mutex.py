"""A borrowed read mutex is a live capability, never an interruption bypass."""
from contextvars import copy_context

import pytest

from specroad.changes._lock_files import LockFiles
from specroad.changes.lock_values import ProjectLockError
from specroad.changes.normal_access import (
    NormalAccessError, normal_read_mutex, require_normal_access,
)
from specroad.changes.write_guard_read import inspect_write_state
from support.model import configuration_file, put
from support.read_only import inventory, no_write_attempts


def test_borrowed_mutex_checks_do_not_release_it_or_create_owner_records(tmp_path):
    configuration_file(tmp_path)
    before = inventory(tmp_path)
    # Real shared observations coexist but neither grant writer authority nor
    # admit an exclusive contender. They leave no persistent project effect.
    with LockFiles(tmp_path) as observer, no_write_attempts():
        with observer.observe_mutex() as busy:
            assert not busy and not observer.held
            require_normal_access(tmp_path)
            with LockFiles(tmp_path) as other, other.observe_mutex() as other_busy:
                assert not other_busy
            with pytest.raises(ProjectLockError):
                observer.require_held()
            with pytest.raises(ProjectLockError):
                observer.acquire()
            with pytest.raises(ProjectLockError):
                with observer.observe_mutex():
                    pytest.fail('A nested observation can release its outer guard')
            with LockFiles(tmp_path) as contender, pytest.raises(ProjectLockError) as blocked:
                contender.acquire()
            assert blocked.value.reason == 'project_lock_busy'
        with LockFiles(tmp_path) as contender:
            contender.acquire()  # No shared guard survived normal completion.
        with pytest.raises(RuntimeError, match='interrupted observation'):
            with observer.observe_mutex():
                raise RuntimeError('interrupted observation')
        with LockFiles(tmp_path) as contender:
            contender.acquire()  # Failed observations release their own guard too.
        observer.acquire()
        observer.require_held()
    assert inventory(tmp_path) == before
    with LockFiles(tmp_path) as held:
        held.acquire()
        with pytest.raises(ProjectLockError):
            with held.observe_mutex():
                pytest.fail('Observation downgraded a borrowed writer mutex')
        with no_write_attempts(), normal_read_mutex(held):
            require_normal_access(tmp_path)
            with LockFiles(tmp_path) as contender, pytest.raises(ProjectLockError) as blocked:
                contender.acquire()
            assert blocked.value.reason == 'project_lock_busy'
        held.require_held()
        # Leaving the observation scope does not release the caller's mutex.
        assert inspect_write_state(tmp_path)['state'] == 'unknown'
        assert inventory(tmp_path) == before
    assert inspect_write_state(tmp_path)['state'] == 'clean'
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('path,state', [
    ('.specroad/unclassified.json', 'unknown'),
    ('.specroad/write-state/pending.json', 'corrupted'),
    ('.specroad/transactions/abandoned/journal.json', 'corrupted'),
])
def test_borrowed_mutex_still_refuses_unknown_files_and_interrupted_writes(tmp_path, path, state):
    configuration_file(tmp_path)
    put(tmp_path, path, b'{"untrusted":"original bytes"}')
    before = inventory(tmp_path)
    with LockFiles(tmp_path) as held:
        held.acquire()
        with normal_read_mutex(held), no_write_attempts(), pytest.raises(NormalAccessError) as error:
            require_normal_access(tmp_path)
        assert error.value.exit_code == 5 and error.value.observation['state'] == state
        assert not error.value.observation['normal_operation_started']
        held.require_held()
    assert inventory(tmp_path) == before


def test_a_mutex_for_another_root_cannot_authorize_project_access(tmp_path):
    first, second = tmp_path / 'first', tmp_path / 'second'
    first.mkdir(); second.mkdir()
    configuration_file(first); configuration_file(second)
    before = inventory(tmp_path)
    with LockFiles(first) as held:
        held.acquire()
        with normal_read_mutex(held), no_write_attempts(), pytest.raises(NormalAccessError) as error:
            require_normal_access(second)
        assert error.value.observation['state'] == 'unknown'
        held.require_held()
    assert inventory(tmp_path) == before


def test_a_saved_context_cannot_reuse_a_released_mutex(tmp_path):
    configuration_file(tmp_path)
    before = inventory(tmp_path)
    with LockFiles(tmp_path) as held:
        held.acquire()
        with normal_read_mutex(held):
            context = copy_context()
    with no_write_attempts(), pytest.raises(NormalAccessError) as error:
        context.run(require_normal_access, tmp_path)
    assert error.value.observation['state'] == 'unknown'
    with pytest.raises(ProjectLockError):
        with normal_read_mutex(held):
            pytest.fail('Released capability entered')
    assert inventory(tmp_path) == before
