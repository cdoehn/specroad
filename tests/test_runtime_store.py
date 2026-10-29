"""Durable phase records, real crash recovery, and arbitrary parallel selections."""
from copy import deepcopy
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time

import pytest

from verification_support.runtime_store import (TimingStore, binding, read_store,
    measurement_from_store)
from verification_support.runtime_runner import choose
from verification_support.runtime_baseline import make_baseline, validate_measurement
from verification_support.identity import source_identity


def sample():
    pairs = {'tests/test_x.py::test_' + str(n): 'case.' + str(n) for n in range(5)}
    return binding('a' * 64, pairs, 2)


def record(store, run, node, *, phases=('setup', 'call', 'teardown'), outcome='passed', duration=0.01):
    for phase in phases:
        store.observe(run, node, store.meta['pairs'][node], phase, duration,
                      outcome if phase == 'call' else 'passed', 'gw0')


def test_every_phase_is_visible_to_an_independent_reader_before_run_end(tmp_path):
    meta = sample();path = tmp_path/'timings.sqlite3'
    store = TimingStore(path, tmp_path/'repo', meta)
    run = store.begin(meta['pairs']);node = next(iter(meta['pairs']))
    try:
        store.observe(run, node, meta['pairs'][node], 'setup', 0.5, 'passed', 'gw0')
        code = 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute("SELECT phase,duration_ns FROM phases").fetchall())'
        checked = subprocess.check_output([sys.executable, '-I', '-B', '-c', code, str(path)])
        assert b"('setup', 500000000)" in checked
        assert not read_store(path, tmp_path/'repo')[1]
        record(store, run, node, phases=('call', 'teardown'))
        assert set(read_store(path, tmp_path/'repo')[1]) == {node}
        assert store.db.execute('PRAGMA synchronous').fetchone()[0] == 2
    finally:store.close()


def test_incomplete_attempts_never_mix_and_first_success_is_not_overwritten(tmp_path):
    meta = sample();path = tmp_path/'data.sqlite3';root = tmp_path/'repo'
    store = TimingStore(path, root, meta);node = next(iter(meta['pairs']))
    try:
        run = store.begin(meta['pairs']);record(store, run, node, phases=('setup', 'call'))
        run = store.begin(meta['pairs']);record(store, run, node, phases=('teardown',))
        assert not read_store(path, root)[1]
        run = store.begin(meta['pairs']);record(store, run, node)
        first = read_store(path, root)[1][node]
        run = store.begin(meta['pairs']);record(store, run, node, duration=99)
        assert read_store(path, root)[1][node] == first
    finally:store.close()


@pytest.mark.parametrize('outcome', ['failed', 'error', 'skipped', 'expected_failure', 'unexpected_success'])
def test_nonpassing_test_remains_missing(tmp_path, outcome):
    meta=sample();path=tmp_path/'data.sqlite3';store=TimingStore(path,tmp_path/'repo',meta)
    try:
        run=store.begin(meta['pairs']);record(store,run,next(iter(meta['pairs'])),outcome=outcome)
        assert not read_store(path,tmp_path/'repo')[1]
        with pytest.raises(ValueError):measurement_from_store(path,tmp_path/'repo','a'*64)
    finally:store.close()


def test_failed_subtest_disqualifies_an_otherwise_complete_parent(tmp_path):
    meta=sample();path=tmp_path/'data.sqlite3';store=TimingStore(path,tmp_path/'repo',meta)
    try:
        run=store.begin(meta['pairs']);node=next(iter(meta['pairs']))
        record(store,run,node)
        store.observe(run,node,meta['pairs'][node],'call',0.2,'failed','gw0',subtest=True)
        assert not read_store(path,tmp_path/'repo')[1]
    finally:store.close()


def test_duplicate_phase_and_changed_source_cannot_yield_coverage(tmp_path):
    meta=sample();path=tmp_path/'data.sqlite3';root=tmp_path/'repo'
    store=TimingStore(path,root,meta)
    try:
        run=store.begin(meta['pairs']);node=next(iter(meta['pairs']));record(store,run,node)
        with pytest.raises(ValueError):record(store,run,node,phases=('setup',))
        assert not read_store(path,root)[1]
        run=store.begin(meta['pairs'])
        for node in meta['pairs']:record(store,run,node)
        with pytest.raises(ValueError):measurement_from_store(path,root,'b'*64)
        result=measurement_from_store(path,root,'a'*64)
        assert result['coverage_complete'] and result['full_suite_passed'] is None
        assert validate_measurement(result) is result
        assert len(make_baseline(result)['excluded_test_ids']) == 1
        store.invalidate(run,'source_changed')
        with pytest.raises(ValueError):measurement_from_store(path,root,'a'*64)
    finally:store.close()


@pytest.mark.parametrize('changed', ['source_sha256', 'pairs', 'workers', 'platform'])
def test_incompatible_measurement_is_rejected_without_changing_saved_rows(tmp_path,changed):
    meta=sample();path=tmp_path/'data.sqlite3';root=tmp_path/'repo'
    store=TimingStore(path,root,meta);run=store.begin(meta['pairs']);record(store,run,next(iter(meta['pairs'])));store.close()
    before=path.read_bytes();other=deepcopy(meta)
    other[changed]={'source_sha256':'b'*64,'pairs':{'node':'id'},'workers':4,'platform':{}}[changed]
    with pytest.raises(ValueError):TimingStore(path,root,other)
    assert path.read_bytes()==before


def test_writer_lock_is_exclusive_and_source_or_link_paths_are_refused(tmp_path):
    root=tmp_path/'repo';root.mkdir();meta=sample();path=tmp_path/'data.sqlite3'
    store=TimingStore(path,root,meta)
    try:
        with pytest.raises(BlockingIOError):TimingStore(path,root,meta)
        link=tmp_path/'link.sqlite3';link.symlink_to(path)
        with pytest.raises(ValueError):TimingStore(link,root,meta)
        with pytest.raises(ValueError):TimingStore(root/'verification/data.sqlite3',root,meta)
    finally:store.close()


def test_free_group_is_union_of_files_stable_ids_and_nodeids(tmp_path):
    pairs={'tests/a.py::a':'alpha','tests/a.py::b':'beta','tests/b.py::x':'gamma','tests/c.py::z':'delta'}
    file=tmp_path/'selection.json';file.write_text(json.dumps({'test_files':['tests/a.py'],'test_ids':['gamma']}))
    assert choose(pairs,identities=['tests/c.py::z','alpha'],selections=[file])==pairs
    with pytest.raises(ValueError):choose(pairs,identities=['missing'])
    with pytest.raises(ValueError):choose(pairs,files=['../tests/a.py'])


CRASH_SOURCE = '''from pathlib import Path
import time

def test_0_fast():
    p=Path('build/fast_count')
    p.write_text(str(int(p.read_text())+1) if p.exists() else '1')

def test_1_wait():
    while not Path('build/release').exists():
        time.sleep(0.02)
'''


def test_real_controller_kill_preserves_completed_test_and_remaining_does_not_repeat_it(tmp_path):
    from support.catalog_project import make_catalog_project,execute
    ids=['tests/test_subject.py::test_0_fast','tests/test_subject.py::test_1_wait']
    root=make_catalog_project(tmp_path,ids=ids,source=CRASH_SOURCE)
    journal=root/'build/timings.sqlite3'
    with (root/'build/interrupted.log').open('wb') as log:
        child=subprocess.Popen([sys.executable,'-I','-B',str(root/'tools/measure_test_runtimes.py'),
            '--journal',str(journal),'--workers','2','--all'],cwd=root,
            stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        try:
            deadline=time.monotonic()+40
            while time.monotonic()<deadline:
                assert child.poll() is None,(root/'build/interrupted.log').read_text()
                try:
                    if ids[0] in read_store(journal,root)[1]:break
                except (OSError,ValueError,sqlite3.Error):pass
                time.sleep(0.05)
            else:raise AssertionError('Completed phase records were not persisted')
        finally:
            if child.poll() is None:os.killpg(child.pid,signal.SIGKILL)
            child.wait(timeout=10)
    assert set(read_store(journal,root)[1])=={ids[0]}
    (root/'build/release').write_text('yes')
    resumed=execute(root,'measure_test_runtimes.py',['--journal',str(journal),'--workers','2','--remaining'])
    assert resumed.returncode==0,resumed.stdout.decode()+resumed.stderr.decode()
    assert (root/'build/fast_count').read_text()=='1'
    meta,complete,info=read_store(journal,root)
    assert set(complete)==set(ids) and info['attempts']==2
    assert len(measurement_from_store(journal,root,source_identity(root))['tests'])==2


def test_real_selected_groups_export_only_after_complete_bound_coverage(tmp_path):
    from support.catalog_project import make_catalog_project,execute,NATIVE_IDS,LEGACY_ID
    root=make_catalog_project(tmp_path);journal=root/'build/timings.sqlite3'
    first=execute(root,'measure_test_runtimes.py',['--journal',str(journal),'--workers','2','--test-id',NATIVE_IDS[0]])
    assert first.returncode==0,first.stderr.decode()
    assert len(read_store(journal,root)[1])==1
    output=root/'build/export.json'
    refused=execute(root,'measure_test_runtimes.py',['--journal',str(journal),'--export',str(output)])
    assert refused.returncode!=0 and not output.exists()
    selection=root/'build/group.json';selection.write_text(json.dumps({'test_files':['tests/test_subject.py'],'test_ids':[LEGACY_ID]}))
    rest=execute(root,'measure_test_runtimes.py',['--journal',str(journal),'--workers','2','--selection-file',str(selection)])
    assert rest.returncode==0,rest.stderr.decode()
    assert len(read_store(journal,root)[1])==4
    exported=execute(root,'measure_test_runtimes.py',['--journal',str(journal),'--export',str(output)])
    assert exported.returncode==0,exported.stderr.decode()
    value=json.loads(output.read_text());assert value['full_suite_passed'] is None and value['coverage_complete']
    assert len(value['tests'])==4


def test_explicit_reopen_recovers_interrupted_sqlite_transaction_without_losing_committed_phases(tmp_path):
    meta=sample();path=tmp_path/'data.sqlite3';root=tmp_path/'repo'
    store=TimingStore(path,root,meta);run=store.begin(meta['pairs']);node=next(iter(meta['pairs']))
    record(store,run,node);store.close()
    program="""import sqlite3,sys,os
c=sqlite3.connect(sys.argv[1]); c.execute('PRAGMA cache_size=1')
c.execute('BEGIN IMMEDIATE')
for n in range(1,200):
    c.execute('INSERT INTO runs(started,error) VALUES(?,?)',('unfinished','x'*8192))
os._exit(17)
"""
    child=subprocess.run([sys.executable,'-I','-B','-c',program,str(path)],check=False)
    assert child.returncode==17 and Path(str(path)+'-journal').exists()
    recovered=TimingStore(path,root,meta)
    try:
        assert set(read_store(path,root)[1])=={node}
        assert recovered.db.execute('SELECT count(*) FROM runs').fetchone()[0]==1
    finally:recovered.close()
