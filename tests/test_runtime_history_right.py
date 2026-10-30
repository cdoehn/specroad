"""Crash, I/O and concurrent native measurement boundaries."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
import sqlite3

import pytest

from verification_support.runtime_history import RuntimeHistory, LOCAL, POLICY, filter_latest
from test_runtime_history import complete


@pytest.mark.parametrize('fault', ['subtest','duplicate','order','worker','identity','skip','xfail','infinite','negative'])
def test_invalid_native_phases_never_replace_failed_current_with_old_success(tmp_path, fault):
    with RuntimeHistory(tmp_path) as store:
        complete(store, store.begin('a'*64, 4), seconds=100)
        run=store.begin('b'*64, 4);node='tests/test_sample.py::case'
        store.start(run,node,'case','gw0')
        phases=('call','setup','teardown') if fault=='order' else ('setup','call','teardown')
        for phase in phases:
            duration=float('inf') if fault=='infinite' else -1 if fault=='negative' else 1
            outcome='skipped' if fault=='skip' else 'expected_failure' if fault=='xfail' else 'passed'
            store.observe(run,node,'wrong' if fault=='identity' else 'case',
                          'gw1' if fault=='worker' else 'gw0',phase,duration,outcome)
        if fault=='subtest':store.observe(run,node,'case','gw0','call',0,'failed',subtest=True)
        if fault=='duplicate':store.observe(run,node,'case','gw0','call',1,'passed')
        assert store.snapshot(['case'])['tests'][0]['duration_ns'] is None


def test_parallel_connections_keep_all_attempts_and_phases(tmp_path):
    with RuntimeHistory(tmp_path):pass
    def measure(i):
        with RuntimeHistory(tmp_path) as store:
            run=store.begin('a'*64,4)
            complete(store,run,f'case.{i}',worker=f'gw{i%4}')
            store.finish(run,0)
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(measure,range(20)))
    with RuntimeHistory(tmp_path) as store:
        assert store.db.execute('SELECT COUNT(*) FROM phases').fetchone()==(60,)
        assert len([r for r in store.snapshot([f'case.{i}' for i in range(20)])['tests']
                    if r['duration_ns'] is not None])==20


def test_database_write_failure_keeps_prior_history_and_current_attempt_invalid(tmp_path):
    with RuntimeHistory(tmp_path) as store:
        complete(store,store.begin('a'*64,4))
        run=store.begin('b'*64,4);node='tests/test_sample.py::case'
        store.start(run,node,'case','gw0')
        store.db.set_authorizer(lambda action,a,b,c,d: sqlite3.SQLITE_DENY
                                if action==sqlite3.SQLITE_INSERT and a=='phases' else sqlite3.SQLITE_OK)
        with pytest.raises(sqlite3.DatabaseError):store.observe(run,node,'case','gw0','setup',1,'passed')
        store.db.set_authorizer(None)
        assert store.snapshot(['case'])['tests'][0]['duration_ns'] is None
        assert store.db.execute('SELECT COUNT(*) FROM phases').fetchone()==(3,)


@pytest.mark.parametrize('kind',['symlink','hardlink','invalid','parent'])
def test_unsafe_store_is_rejected_without_modifying_other_file(tmp_path,kind):
    other=tmp_path/'original';other.write_bytes(b'preserve this')
    target=tmp_path/LOCAL;target.parent.mkdir()
    if kind=='symlink':target.symlink_to(other)
    elif kind=='hardlink':os.link(other,target)
    elif kind=='invalid':target.write_bytes(b'not a database')
    else:
        target.parent.rmdir();target.parent.symlink_to(tmp_path,target_is_directory=True)
    with pytest.raises((OSError,ValueError,sqlite3.DatabaseError)):RuntimeHistory(tmp_path)
    assert other.read_bytes()==b'preserve this'


@pytest.mark.parametrize('fault',['extra','bool','negative','origin','duplicate','unknown'])
def test_invalid_selection_snapshot_cannot_hide_tests(tmp_path,fault):
    with RuntimeHistory(tmp_path) as store:
        complete(store,store.begin('a'*64,4))
        snapshot=store.snapshot(['case'])
    row=snapshot['tests'][0]
    if fault=='extra':row['hidden']=True
    elif fault=='bool':row['duration_ns']=True
    elif fault=='negative':row['duration_ns']=-1
    elif fault=='origin':row.pop('attempt');row['origin_sha256']='x'*64
    elif fault=='duplicate':snapshot['tests'].append(deepcopy(row))
    else:row['test_id']='other'
    with pytest.raises(ValueError):filter_latest({'node':'case'},snapshot)


def test_history_replacement_cannot_support_a_successful_gate(tmp_path):
    with RuntimeHistory(tmp_path) as store:
        run=store.begin('a'*64,4);node=complete(store,run)
        store.path.rename(store.path.with_suffix('.preserved'))
        store.path.write_bytes(b'replaced')
        with pytest.raises(ValueError):store.verify_run(run,{node:'case'},{'case':'passed'})


def test_finished_run_cannot_receive_another_test_start(tmp_path):
    with RuntimeHistory(tmp_path) as store:
        run=store.begin('a'*64,4);store.finish(run,0)
        with pytest.raises(ValueError):store.start(run,'node','case','gw0')


def test_real_worker_crash_invalidates_previous_value_and_retry_records_new_success(tmp_path):
    from support.catalog_project import make_catalog_project,execute,SOURCE,NATIVE_IDS,LEGACY_ID
    root=make_catalog_project(tmp_path)
    args=['--workers','2','--expected-tests','4','--test-file','tests/test_subject.py']
    first=execute(root,'run_selected_tests.py',[*args,'--outdir',str(root/'build/first')])
    assert first.returncode==0,(first.stdout+first.stderr).decode()
    test=root/'tests/test_subject.py'
    test.write_text(SOURCE.replace('def test_native():','def test_native():\n    import os; os._exit(7)'))
    crash=execute(root,'run_selected_tests.py',[*args,'--outdir',str(root/'build/crash')])
    assert crash.returncode!=0
    with RuntimeHistory(root) as store:
        assert store.snapshot([NATIVE_IDS[0]])['tests'][0]['duration_ns'] is None
        assert store.db.execute('SELECT COUNT(*) FROM attempts WHERE test=?',(NATIVE_IDS[0],)).fetchone()==(2,)
    test.write_text(SOURCE)
    retry=execute(root,'run_selected_tests.py',[*args,'--outdir',str(root/'build/retry')])
    assert retry.returncode==0,(retry.stdout+retry.stderr).decode()
    with RuntimeHistory(root) as store:
        assert store.snapshot([NATIVE_IDS[0]])['tests'][0]['duration_ns'] is not None
        assert store.db.execute('SELECT COUNT(*) FROM attempts WHERE test=?',(NATIVE_IDS[0],)).fetchone()==(3,)


def test_real_collection_has_no_history_and_corrupt_store_prevents_test_bodies(tmp_path):
    from support.catalog_project import make_catalog_project,execute,check,effects
    root=make_catalog_project(tmp_path)
    code,report=check(root)
    assert code==0 and not (root/LOCAL).exists()
    (root/LOCAL).write_bytes(b'damaged database')
    result=execute(root,'run_selected_tests.py',['--workers','2','--expected-tests','4',
        '--test-file','tests/test_subject.py','--outdir',str(root/'build/rejected')])
    assert result.returncode!=0 and effects(root)==[]
    assert (root/LOCAL).read_bytes()==b'damaged database'
