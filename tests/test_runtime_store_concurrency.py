"""A live reader must not abort phase persistence; imported timing origins stay explicit."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading

import pytest

from verification_support import runtime_store as module
from verification_support.runtime_store import TimingStore,read_store
from verification_support.runtime_baseline import make_baseline,validate_baseline,validate_measurement
from test_runtime_store import sample,record
from test_runtime_baseline import measurement


def test_native_writer_waits_for_an_existing_reader_then_commits(tmp_path):
    meta=sample();path=tmp_path/'data.sqlite3';root=tmp_path/'repo'
    store=TimingStore(path,root,meta);run=store.begin(meta['pairs']);store.close()
    reader=sqlite3.connect(path);reader.execute('BEGIN');reader.execute('SELECT count(*) FROM phases').fetchone()
    tools=Path(__file__).resolve().parents[1]/'tools'
    program='''import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from verification_support.runtime_store import TimingStore
s=TimingStore(Path(sys.argv[2]),Path(sys.argv[3]),json.loads(sys.argv[4]))
print('ready',flush=True)
sys.stdin.readline()
node=next(iter(s.meta['pairs']))
s.observe(int(sys.argv[5]),node,s.meta['pairs'][node],'setup',0.25,'passed','gw0')
print('committed',flush=True)
s.close()
'''
    child=subprocess.Popen([sys.executable,'-I','-B','-c',program,str(tools),str(path),str(root),json.dumps(meta),str(run)],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        assert child.stdout.readline().strip()=='ready'
        child.stdin.write('write\n');child.stdin.flush()
        with pytest.raises(subprocess.TimeoutExpired):child.wait(timeout=0.3)
        reader.rollback()
        output,error=child.communicate(timeout=10)
        assert child.returncode==0,(output,error)
        assert 'committed' in output
        assert read_store(path,root)[2]['persisted_phases']==1
    finally:
        reader.close()
        if child.poll() is None:child.kill();child.wait(timeout=5)


def test_slow_status_analysis_holds_no_lock_on_the_live_journal(tmp_path,monkeypatch):
    meta=sample();path=tmp_path/'data.sqlite3';root=tmp_path/'repo'
    store=TimingStore(path,root,meta);run=store.begin(meta['pairs'])
    entered=threading.Event();release=threading.Event();observations=[]
    original=module._completed
    def slow(db,metadata):
        entered.set()
        assert release.wait(5)
        return original(db,metadata)
    monkeypatch.setattr(module,'_completed',slow)
    def read():observations.append(read_store(path,root))
    reader=threading.Thread(target=read);reader.start()
    try:
        assert entered.wait(5)
        # No busy timeout: this proves the status computation has released
        # the original file, rather than merely tolerating a short blockage.
        db=sqlite3.connect(path,timeout=0)
        try:
            with db:db.execute('UPDATE runs SET error=? WHERE id=?',('probe',run))
        finally:db.close()
        record(store,run,next(iter(meta['pairs'])))
    finally:
        release.set();reader.join(timeout=5);store.close()
    assert not reader.is_alive() and len(observations)==1
    assert observations[0][2]['persisted_phases']==0
    assert len(read_store(path,root)[1])==1


def imported_measurement():
    old=measurement(10)
    old.update(format_version=3,kind='specroad-resumable-test-runtimes-v3',
               coverage_complete=True,full_suite_passed=None,attempts=2)
    old['measurement_imports']=[{'from_source_sha256':'b'*64,'to_source_sha256':'a'*64,
        'source_journal_sha256':'c'*64,'input_inventory_sha256':'d'*64,
        'imported_test_ids':['case.0','case.1'],
        'changed_files':[{'path':'tools/verification_support/runtime_store.py','before':'e'*64,'after':'f'*64}]}]
    return old


def test_historical_origins_survive_measurement_export_and_frozen_list():
    value=imported_measurement()
    assert validate_measurement(value) is value
    baseline=make_baseline(value)
    assert baseline['format_version']==2
    assert baseline['measurement_imports']==value['measurement_imports']
    assert validate_baseline(baseline) is baseline
    assert baseline['excluded_test_ids']==['case.8','case.9']


@pytest.mark.parametrize('fault',['missing','target','same_source','foreign_id','duplicate','path','hash','kind'])
def test_invalid_provenance_cannot_become_a_current_baseline(fault):
    value=imported_measurement();entry=value['measurement_imports'][0]
    if fault=='missing':value.pop('measurement_imports')
    elif fault=='target':entry['to_source_sha256']='f'*64
    elif fault=='same_source':entry['from_source_sha256']='a'*64
    elif fault=='foreign_id':entry['imported_test_ids']=['absent']
    elif fault=='duplicate':entry['imported_test_ids']=['case.0','case.0']
    elif fault=='path':entry['changed_files'][0]['path']='../foreign'
    elif fault=='hash':entry['source_journal_sha256']='invalid'
    else:value['kind']='unknown'
    with pytest.raises(ValueError):make_baseline(value)
