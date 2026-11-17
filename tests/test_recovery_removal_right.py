"""Retained repair data cannot become native execution or owner authority.

The old Work identities are explicit inert fixtures in actual, coherently
rehashed containers. Interrupted publication uses the real writer and an I/O
cut; no validator or successful result is replaced.
"""
import importlib
import os

import pytest

from specroad import changes
from specroad.changes import project_lock, ProjectLockError, transaction_preflight
from specroad.changes._lock_process import LinuxOwnerProbe
from specroad.cli.contracts import CommandClass
from specroad.work._archive import ArchiveError
from specroad.work.packages import export_work_package
from support.legacy_publication import partial_commit
from support.read_only import inventory, no_write_attempts
from test_project_locks_right import stale
from test_work_packages import unpack, restore
from test_work_packages_right import altered_initial
from test_work_resume import recorded, setup


@pytest.mark.parametrize('identity', ['command', 'class', 'both'])
def test_old_restore_package_is_rejected_before_target_allocation(recorded, tmp_path, identity):
    _, roots, _, store = setup(tmp_path)
    metadata, payloads = unpack(export_work_package(store))

    def change(value):
        if identity in ('command', 'both'):
            value['command_id'] = 'recover.restore'
        if identity in ('class', 'both'):
            value['command_class'] = 'recovery_write'

    raw = altered_initial(metadata, payloads, change)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ArchiveError) as caught:
        restore(raw, roots, tmp_path / 'rejected')
    assert caught.value.reason == 'invalid_work_package'
    assert inventory(tmp_path) == before and not (tmp_path / 'rejected').exists()


@pytest.mark.parametrize('command', ['recover run', 'recover discard', 'recover restore'])
@pytest.mark.parametrize('state', ['interrupted', 'stale-owner', 'unknown-owner'])
def test_old_lock_class_cannot_take_over_or_repair_native_state(tmp_path, command, state):
    if state == 'interrupted':
        _, _, journal = partial_commit(tmp_path)
        assert journal.data['published_count'] == 1
    else:
        stale(tmp_path, **({'host_id': None, 'process_start_id': None}
                          if state == 'unknown-owner' else {'host_id': LinuxOwnerProbe().current().host_id,
                                'process_id': os.getpid(), 'process_start_id': 'retired-start'}))
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ProjectLockError) as caught:
        with project_lock(tmp_path, kind='recovery', command=command,
                          project_id='sample', transaction_id='retained-legacy'):
            pytest.fail('Retired Recovery obtained a native lock')
    assert caught.value.reason == 'product_recovery_removed' and caught.value.exit_code == 2
    with no_write_attempts():
        result = transaction_preflight(tmp_path, command_class=CommandClass.READ_ONLY)
    assert result.exit_code == 5
    assert result.data['reason'] == ('project_unknown' if state == 'unknown-owner'
                                     else 'project_corrupted')
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('name', [
    'prepare_discard_recovery', 'discard_unpublished_transaction',
    'complete_published_transaction', 'rollback_interrupted_transaction',
    'transaction_recovery_lock', 'cleanup_recovered_transaction',
])
def test_retired_mutator_is_not_an_exported_host_api(name):
    assert not hasattr(changes, name) and name not in changes.__all__


@pytest.mark.parametrize('module', [
    'specroad.recovery', 'specroad.work.restore', 'specroad.cli.restore_handler',
    'specroad.changes.recovery', 'specroad.changes.recovery_lock',
    'specroad.changes.recovery_cleanup', 'specroad.changes._automatic_recovery',
])
def test_retired_execution_module_cannot_be_imported(module):
    try:
        loaded = importlib.import_module(module)
    except ModuleNotFoundError as error:
        assert error.name == module
    else:
        # File deletion may leave an empty directory. A namespace is not an
        # executable repair package and must expose none of its former APIs.
        assert module == 'specroad.recovery' and loaded.__spec__.origin is None
        assert not any(hasattr(loaded, name) for name in (
            'prepare_restore_plan', 'execute_restore_plan', 'RestoreServices'))
