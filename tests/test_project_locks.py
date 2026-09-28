"""Real cross-process exclusion, ownership metadata and read-only observation."""
import copy
import json
import os
import pickle
from pathlib import Path
from uuid import UUID
import pytest
from specroad.changes import (project_lock, inspect_project_lock, ProjectLockError,
                               LockRecord, LockKind)
from specroad.storage.read_only import validate_project_read_only
from tests.support.model import put
from tests.support.read_only import make_project, inventory, no_write_attempts, profile_resources
from tests.support.model_validation import artifact
from tests.support.project_locks import options, attempt, orphan, Probe


def test_real_writer_lock_and_release(tmp_path):
    make_project(tmp_path)
    with project_lock(tmp_path, **options()) as lock:
        assert lock.check() is True
        assert (tmp_path / '.specroad/locks/project.json').is_file()
    assert not (tmp_path / '.specroad/locks/project.json').exists()
    assert attempt(tmp_path)['acquired'] is True
    with pytest.raises(ProjectLockError):
        lock.check()


@pytest.mark.parametrize('first', ['writer', 'recovery', 'operational'])
@pytest.mark.parametrize('second', ['writer', 'recovery', 'operational'])
def test_all_lock_kinds_share_one_real_mutex(tmp_path, first, second):
    make_project(tmp_path)
    with project_lock(tmp_path, **options(first)) as lock:
        assert attempt(tmp_path, second) == {'acquired': False, 'reason': 'project_lock_busy'}
        assert lock.check()
    assert attempt(tmp_path, second)['acquired']


def test_same_process_second_open_cannot_bypass_mutex(tmp_path):
    make_project(tmp_path)
    with project_lock(tmp_path, **options()):
        with pytest.raises(ProjectLockError) as caught:
            with project_lock(tmp_path, **options('recovery')):
                pytest.fail('must not enter')
        assert caught.value.reason == 'project_lock_busy'


def test_independent_project_roots_do_not_block_each_other(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'; a.mkdir(); b.mkdir()
    make_project(a); make_project(b)
    with project_lock(a, **options()):
        assert attempt(b)['acquired']


def test_record_carries_complete_binding(tmp_path):
    make_project(tmp_path)
    with project_lock(tmp_path, **options()) as held:
        value = held.record.data
        assert set(value) == {'format_version','kind','lock_id','project_id','root_identity',
            'host_id','process_id','process_start_id','created_at','command','request_id','transaction_id'}
        assert UUID(value['lock_id']).version == 4
        assert value['process_id'] == os.getpid()
        assert value['root_identity'] == {'device':str(tmp_path.stat().st_dev),'inode':str(tmp_path.stat().st_ino)}
        assert value['request_id'] == 'Req.Test:1' and value['transaction_id'] == 'txn-test'
        assert value['created_at'].endswith('Z')
        assert (tmp_path / '.specroad/locks/project.json').stat().st_mode & 0o777 == 0o600
        view = held.record.data; view['process_id'] = 1
        assert held.record.data == value
        assert LockRecord(held.record.source_bytes).source_bytes == held.record.source_bytes


def test_exception_releases_only_owned_record(tmp_path):
    make_project(tmp_path)
    with pytest.raises(LookupError):
        with project_lock(tmp_path, **options()):
            raise LookupError('body')
    assert attempt(tmp_path)['acquired']


def test_status_is_read_only_and_does_not_grant_exclusion(tmp_path):
    make_project(tmp_path)
    before = inventory(tmp_path)
    with no_write_attempts():
        status = inspect_project_lock(tmp_path).data
    assert inventory(tmp_path) == before
    assert status['owner_state'] == 'absent'
    assert not status['exclusive_access_proven'] and not status['write_authorized']


def test_status_of_alive_writer_never_removes_record(tmp_path):
    make_project(tmp_path)
    with project_lock(tmp_path, **options()) as held:
        v = held.record.data
        before = inventory(tmp_path)
        with no_write_attempts():
            status = inspect_project_lock(tmp_path, owner_probe=Probe(v['host_id'], 'alive', v['process_start_id'])).data
        assert status['owner_state'] in ('alive', 'unverifiable')
        assert status['record'] == v and status['record_sha256'] == held.record.sha256
        assert inventory(tmp_path) == before


def test_status_can_read_a_broken_configuration(tmp_path):
    put(tmp_path, 'specroad.json', b'broken')
    with no_write_attempts():
        assert inspect_project_lock(tmp_path).data['owner_state'] == 'absent'


def test_writer_rejects_wrong_project_id_without_files(tmp_path):
    make_project(tmp_path); before = inventory(tmp_path)
    with pytest.raises(Exception):
        with project_lock(tmp_path, **{**options(), 'project_id':'different'}):
            pytest.fail('entered')
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('override', [dict(kind='read'), dict(command='recover run'),
    dict(kind='recovery', command='change apply'), dict(kind=True), dict(command=['change apply']),
    dict(request_id='bad request'), dict(request_id=5), dict(transaction_id=None)])
def test_bad_request_is_rejected_before_writes(tmp_path, override):
    make_project(tmp_path); before = inventory(tmp_path)
    with pytest.raises((ValueError, TypeError)):
        with project_lock(tmp_path, **{**options(), **override}):
            pytest.fail('entered')
    assert inventory(tmp_path) == before


def test_abrupt_child_exit_leaves_record_for_explicit_recovery(tmp_path):
    make_project(tmp_path)
    old = orphan(tmp_path)
    assert old['process_id'] != os.getpid()
    assert attempt(tmp_path) == {'acquired': False, 'reason':'lock_recovery_required'}
    assert json.loads((tmp_path / '.specroad/locks/project.json').read_bytes()) == old


@pytest.mark.parametrize('name', ['.specroad/transactions/pending.json', '.specroad/recovery/pending.json', '.specroad/unknown.json'])
def test_writer_never_ignores_unresolved_operational_entries(tmp_path, name):
    make_project(tmp_path); put(tmp_path, name)
    before=inventory(tmp_path)
    with pytest.raises(ProjectLockError) as caught:
        with project_lock(tmp_path, **options()):
            pytest.fail('entered')
    assert caught.value.reason == 'transaction_journal_blocks_lock'
    assert inventory(tmp_path)==before


def test_recovery_uses_same_mutex_without_normal_model_loading(tmp_path):
    put(tmp_path, 'specroad.json', b'broken'); journal=put(tmp_path, '.specroad/transactions/pending.json')
    with project_lock(tmp_path, **options('recovery')) as held:
        assert held.check()
        assert attempt(tmp_path, 'recovery')['reason']=='project_lock_busy'
        assert journal.read_bytes()==b'{}'
    assert journal.read_bytes()==b'{}'


def test_completed_receipt_namespace_does_not_act_as_pending_journal(tmp_path):
    make_project(tmp_path); put(tmp_path,'.specroad/transactions/receipts/completed.json',b'passive')
    with project_lock(tmp_path, **options()) as held:
        assert held.check()


def test_unknown_lock_entries_are_preserved(tmp_path):
    make_project(tmp_path); put(tmp_path,'.specroad/locks/foreign.json')
    before=inventory(tmp_path)
    with pytest.raises(ProjectLockError):
        with project_lock(tmp_path, **options()):
            pytest.fail('entered')
    assert inventory(tmp_path)==before


def test_metadata_corruption_is_not_lock_absence(tmp_path):
    make_project(tmp_path); put(tmp_path,'.specroad/locks/project.json',b'{')
    before=inventory(tmp_path)
    with pytest.raises(ProjectLockError):
        inspect_project_lock(tmp_path)
    with pytest.raises(ProjectLockError):
        with project_lock(tmp_path, **options()):
            pytest.fail('entered')
    assert inventory(tmp_path)==before


def test_removed_owned_record_is_not_recreated_during_release(tmp_path):
    make_project(tmp_path)
    with pytest.raises((ProjectLockError, FileNotFoundError)):
        with project_lock(tmp_path, **options()):
            (tmp_path/'.specroad/locks/project.json').unlink()
    assert not (tmp_path/'.specroad/locks/project.json').exists()
    assert attempt(tmp_path)['acquired']


def test_replacement_owner_record_is_not_deleted(tmp_path):
    make_project(tmp_path); path=tmp_path/'.specroad/locks/project.json'
    replacement=None
    with pytest.raises(ProjectLockError):
        with project_lock(tmp_path, **options()) as held:
            replacement=held.record.data; replacement['transaction_id']='replacement'
            path.write_text(json.dumps(replacement))
    assert json.loads(path.read_bytes())==replacement
    assert attempt(tmp_path)['reason']=='lock_recovery_required'


def test_live_handle_is_not_copyable_or_pickleable(tmp_path):
    make_project(tmp_path)
    with project_lock(tmp_path, **options()) as held:
        for operation in (copy.copy, copy.deepcopy, pickle.dumps):
            with pytest.raises(TypeError):
                operation(held)
        assert held.check()


def test_empty_lock_directory_after_release_does_not_block_read_only_validation(tmp_path):
    make_project(tmp_path, artifact())
    with project_lock(tmp_path, **options()):
        pass
    before=inventory(tmp_path)
    with no_write_attempts():
        result=validate_project_read_only(tmp_path,profile_resources=profile_resources(),core_key='core@0.2.0')
    assert result.passed and inventory(tmp_path)==before


def test_active_record_blocks_normal_read_only_model_but_not_diagnosis(tmp_path):
    make_project(tmp_path,artifact())
    with project_lock(tmp_path, **options()) as held:
        before=inventory(tmp_path)
        with no_write_attempts():
            r=validate_project_read_only(tmp_path,profile_resources=profile_resources(),core_key='core@0.2.0')
        assert not r.passed and not r.data['model_loaded']
        assert inventory(tmp_path)==before and held.check()
