"""Audited recovery, uncertain ownership and adversarial native-file events."""
from contextlib import contextmanager
import errno
import io
import json
import os
from pathlib import Path
import stat
import subprocess
from unittest.mock import patch
import pytest
from specroad.changes import (project_lock, recover_project_lock, inspect_project_lock,
    LockRecord, ProjectLockError)
from specroad.changes.locking import observe_owner
from specroad.changes._lock_files import LockFiles
from specroad.changes._lock_process import LinuxOwnerProbe, _proc_stat
from specroad.model.canonical import canonical_json_bytes
from specroad.security import SafetyViolation
from tests.support.project_locks import options, attempt, orphan, Probe, child_program
from tests.support.read_only import make_project, inventory, no_write_attempts, profile_resources
from tests.support.model import put
from tests.support.model_validation import artifact
from specroad.storage.read_only import validate_project_read_only


def stale(root, **changes):
    make_project(root)
    with project_lock(root, **options()) as held:
        data = held.record.data
    data.update(host_id='known-host', process_id=1234, process_start_id='original-start')
    data.update(changes)
    raw = canonical_json_bytes(data)
    put(root, '.specroad/locks/project.json', raw)
    return LockRecord(raw)


def recover(root, record, **kw):
    args={'project_id':'sample', 'expected_lock_sha256':record.sha256,
          'actor':{'actor_type':'human','actor_id':'test-owner'}, 'reason':'Explicit orphan check',
          'force':True, 'owner_probe':Probe('known-host','absent')}
    args.update(kw)
    return recover_project_lock(root, **args)


def test_dead_owner_recovery_audited_and_new_writer_can_enter(tmp_path):
    record=stale(tmp_path); before_config=(tmp_path/'specroad.json').read_bytes()
    result=recover(tmp_path,record).data
    assert result['record_removed'] and not result['new_lock_acquired']
    assert not result['write_authorized'] and not result['actor_authenticated']
    events=[json.loads((tmp_path/result[k]).read_bytes()) for k in ('intent_path','completion_path')]
    assert [e['phase'] for e in events]==['intent','completed']
    assert [e['record_removed'] for e in events]==[False,True]
    assert all(e['old_record']==record.data and e['old_record_sha256']==record.sha256 for e in events)
    assert all(e['actor']=={'actor_type':'human','actor_id':'test-owner'} for e in events)
    assert all((tmp_path/result[k]).stat().st_mode & 0o777 == 0o600 for k in ('intent_path','completion_path'))
    audit_before={p:p.read_bytes() for p in (tmp_path/'.specroad/recovery/lock-audit').iterdir()}
    assert attempt(tmp_path)['acquired']
    assert (tmp_path/'specroad.json').read_bytes()==before_config
    assert audit_before=={p:p.read_bytes() for p in audit_before}


def test_native_abrupt_exit_requires_explicit_recovery_then_reacquires(tmp_path):
    make_project(tmp_path); orphan(tmp_path)
    record=LockRecord((tmp_path/'.specroad/locks/project.json').read_bytes())
    assert attempt(tmp_path)['reason']=='lock_recovery_required'
    result=recover(tmp_path,record,owner_probe=LinuxOwnerProbe(),accept_remote_risk=True).data
    assert result['record_removed'] and attempt(tmp_path)['acquired']


@pytest.mark.parametrize('risk', [False,True])
def test_live_same_host_owner_never_recovered_even_with_acknowledgement(tmp_path,risk):
    record=stale(tmp_path); before=inventory(tmp_path)
    with pytest.raises(ProjectLockError) as e:
        recover(tmp_path,record,owner_probe=Probe('known-host','alive','original-start'),accept_remote_risk=risk)
    assert e.value.reason=='live_owner_recovery_denied'
    assert inventory(tmp_path)==before


@pytest.mark.parametrize('probe,changes,expected', [
    (Probe('foreign','absent'),{},'foreign'),
    (Probe(None,'absent'),{},'unverifiable'),
    (Probe('known-host','unknown'),{},'unverifiable'),
    (Probe('known-host','alive','new-start'),{},'pid_reused'),
    (Probe('known-host','dead','new-start'),{},'pid_reused'),
    (Probe('known-host','alive','original-start'),{'host_id':None},'unverifiable'),
    (Probe('known-host','absent'),{'process_start_id':None},'unverifiable')])
def test_unknown_foreign_or_reused_identity_needs_explicit_risk(tmp_path,probe,changes,expected):
    record=stale(tmp_path,**changes); before=inventory(tmp_path)
    assert observe_owner(record,probe)==expected
    with pytest.raises(ProjectLockError) as e:recover(tmp_path,record,owner_probe=probe)
    assert e.value.reason=='accept_remote_risk_required' and inventory(tmp_path)==before
    result=recover(tmp_path,record,owner_probe=probe,accept_remote_risk=True).data
    assert result['record_removed'] and result['observed_owner_state']==expected


def test_native_mutex_blocks_even_forged_dead_owner_and_force(tmp_path):
    make_project(tmp_path)
    with project_lock(tmp_path,**options()) as held:
        before=inventory(tmp_path)
        with pytest.raises(ProjectLockError) as e:
            recover(tmp_path,held.record,accept_remote_risk=True)
        assert e.value.reason=='project_lock_busy'
        assert held.check() and inventory(tmp_path)==before


@pytest.mark.parametrize('journal', ['.specroad/transactions/tx.json','.specroad/recovery/pending.json','.specroad/unknown.json'])
def test_force_never_bypasses_any_transaction_journal(tmp_path,journal):
    record=stale(tmp_path); put(tmp_path,journal,b'{"state":"complete"}')
    before=inventory(tmp_path)
    with pytest.raises(ProjectLockError) as e:recover(tmp_path,record,accept_remote_risk=True)
    assert e.value.reason=='transaction_journal_blocks_lock' and inventory(tmp_path)==before


def test_recovery_rechecks_journals_after_persisting_intent(tmp_path):
    record=stale(tmp_path); original=LockFiles.append_audit
    def write(files,event,phase,raw):
        result=original(files,event,phase,raw)
        if phase=='intent':put(tmp_path,'.specroad/transactions/late.json')
        return result
    with patch.object(LockFiles,'append_audit',write):
        with pytest.raises(ProjectLockError) as e:recover(tmp_path,record)
    assert e.value.reason=='transaction_journal_blocks_lock' and e.value.mutation_possible
    assert (tmp_path/'.specroad/locks/project.json').read_bytes()==record.source_bytes
    events=[json.loads(p.read_bytes()) for p in (tmp_path/'.specroad/recovery/lock-audit').iterdir()]
    assert len(events)==1 and not events[0]['record_removed']


def test_owner_becoming_live_on_final_observation_prevents_removal(tmp_path):
    record=stale(tmp_path)
    class Changing(Probe):
        calls=0
        def process(self,pid):
            self.calls+=1
            return ('absent',None) if self.calls==1 else ('alive','original-start')
    with pytest.raises(ProjectLockError) as e:recover(tmp_path,record,owner_probe=Changing('known-host'))
    assert e.value.reason=='live_owner_recovery_denied'
    assert (tmp_path/'.specroad/locks/project.json').read_bytes()==record.source_bytes


def test_replacement_record_after_audit_is_preserved(tmp_path):
    record=stale(tmp_path); original=LockFiles.append_audit; new={**record.data,'transaction_id':'other'}
    def change(files,event,phase,raw):
        result=original(files,event,phase,raw)
        put(tmp_path,'.specroad/locks/project.json',canonical_json_bytes(new))
        return result
    with patch.object(LockFiles,'append_audit',change):
        with pytest.raises(ProjectLockError) as e:recover(tmp_path,record)
    assert e.value.reason=='lock_owner_changed'
    assert json.loads((tmp_path/'.specroad/locks/project.json').read_bytes())==new


def test_audit_write_failure_retains_orphan_and_reports_uncertainty(tmp_path):
    record=stale(tmp_path)
    with patch.object(LockFiles,'append_audit',side_effect=OSError(errno.ENOSPC,'full')):
        with pytest.raises(ProjectLockError) as e:recover(tmp_path,record)
    assert e.value.mutation_possible and (tmp_path/'.specroad/locks/project.json').read_bytes()==record.source_bytes


def test_lost_completion_does_not_claim_recovery_did_nothing(tmp_path):
    record=stale(tmp_path); original=LockFiles.append_audit
    def write(files,event,phase,raw):
        if phase=='completed':raise OSError(errno.ENOSPC,'full')
        return original(files,event,phase,raw)
    with patch.object(LockFiles,'append_audit',write):
        with pytest.raises(ProjectLockError) as e:recover(tmp_path,record)
    assert e.value.mutation_possible and not (tmp_path/'.specroad/locks/project.json').exists()
    events=list((tmp_path/'.specroad/recovery/lock-audit').iterdir())
    assert len(events)==1 and not json.loads(events[0].read_bytes())['record_removed']


def test_recovery_requires_exact_bytes_and_root_not_only_owner_pid(tmp_path):
    record=stale(tmp_path); before=inventory(tmp_path)
    for kw in ({'expected_lock_sha256':'0'*64},{'project_id':'other'}):
        with pytest.raises(ProjectLockError):recover(tmp_path,record,**kw)
        assert inventory(tmp_path)==before
    modified=record.data;modified['root_identity']['inode']='0'
    changed=LockRecord(canonical_json_bytes(modified));put(tmp_path,'.specroad/locks/project.json',changed.source_bytes)
    with pytest.raises(ProjectLockError) as e:recover(tmp_path,changed,accept_remote_risk=True)
    assert e.value.reason=='lock_project_binding_mismatch'


@pytest.mark.parametrize('kw',[{'force':False},{'force':1},{'accept_remote_risk':1},
    {'reason':''},{'expected_lock_sha256':'short'},{'actor':{'actor_type':'human'}}, {'actor':None}])
def test_invalid_recovery_requests_do_not_create_files(tmp_path,kw):
    record=stale(tmp_path); before=inventory(tmp_path)
    with pytest.raises((ValueError,TypeError)):recover(tmp_path,record,**kw)
    assert inventory(tmp_path)==before


def test_recovery_does_not_delete_or_rewrite_existing_audit_history(tmp_path):
    record=stale(tmp_path); result=recover(tmp_path,record).data
    first={p:p.read_bytes() for p in (tmp_path/'.specroad/recovery/lock-audit').iterdir()}
    # A later independent crash has a new lock identity and a separate audit pair.
    record=stale(tmp_path); recover(tmp_path,record)
    assert all(p.read_bytes()==raw for p,raw in first.items())
    assert len(list((tmp_path/'.specroad/recovery/lock-audit').iterdir()))==4


@pytest.mark.parametrize('part',['.specroad','.specroad/locks','.specroad/locks/project.json'])
def test_symlinks_never_redirect_lock_reads_or_writes(tmp_path,part):
    root=tmp_path/'root';root.mkdir();make_project(root)
    outside=tmp_path/'outside';outside.mkdir();(outside/'project.json').write_text('sentinel')
    target=root/part;target.parent.mkdir(parents=True,exist_ok=True)
    target.symlink_to(outside/'project.json' if part.endswith('.json') else outside)
    before=inventory(outside)
    with pytest.raises((ProjectLockError,SafetyViolation)):
        with project_lock(root,**options()):pytest.fail('entered')
    assert inventory(outside)==before


def test_hardlinked_record_is_not_read_or_removed(tmp_path):
    record=stale(tmp_path);path=tmp_path/'.specroad/locks/project.json'
    os.link(path,tmp_path/'other-link')
    with pytest.raises(ProjectLockError):recover(tmp_path,record,accept_remote_risk=True)
    assert path.read_bytes()==record.source_bytes and path.stat().st_nlink==2


def test_special_file_is_rejected_without_waiting_for_fifo_peer(tmp_path):
    make_project(tmp_path);p=tmp_path/'.specroad/locks';p.mkdir(parents=True)
    os.mkfifo(p/'project.json')
    with pytest.raises((ProjectLockError,SafetyViolation)):inspect_project_lock(tmp_path)
    assert stat.S_ISFIFO((p/'project.json').lstat().st_mode)


def test_nested_project_in_lock_path_is_not_accepted(tmp_path):
    make_project(tmp_path);put(tmp_path,'.specroad/locks/specroad.json')
    with pytest.raises(ProjectLockError) as e:
        with project_lock(tmp_path,**options()):pytest.fail('entered')
    assert e.value.reason=='nested_lock_project'


def test_replacing_root_during_hold_does_not_mutate_new_root(tmp_path):
    root=tmp_path/'root';root.mkdir();make_project(root)
    old=tmp_path/'old'
    with pytest.raises((ProjectLockError,SafetyViolation)):
        with project_lock(root,**options()):
            root.rename(old);root.mkdir();make_project(root)
    assert not (root/'.specroad').exists()
    assert (old/'.specroad/locks/project.json').exists()


def test_fork_child_cannot_release_parent_mutex_or_owner_record(tmp_path):
    make_project(tmp_path)
    # Fork happens in an isolated child interpreter, never in a pytest worker.
    code='''
import os, json
from specroad.changes import project_lock, ProjectLockError
ctx=project_lock(sys.argv[1],**json.loads(sys.argv[2]));held=ctx.__enter__()
a,b=os.pipe();pid=os.fork()
if pid==0:
    os.close(a)
    try:
        held.check(); outcome=False
    except ProjectLockError:
        outcome=True
    ctx.__exit__(None,None,None)
    os.write(b, b'yes' if outcome else b'no');os.close(b);os._exit(0)
os.close(b);outcome=os.read(a,16);os.close(a);os.waitpid(pid,0)
held.check()
try:
    with project_lock(sys.argv[1],**json.loads(sys.argv[2])):raise AssertionError('double writer')
except ProjectLockError as exc:assert exc.reason=='project_lock_busy'
assert outcome==b'yes'
ctx.__exit__(None,None,None)
'''
    done=subprocess.run(child_program(code,tmp_path,json.dumps(options())),capture_output=True,text=True)
    assert done.returncode==0,done.stderr
    assert attempt(tmp_path)['acquired']


def test_simultaneous_child_contenders_cannot_both_enter(tmp_path):
    make_project(tmp_path)
    code='''
import json
from specroad.changes import project_lock, ProjectLockError
sys.stdin.readline()
try:
    with project_lock(sys.argv[1], **json.loads(sys.argv[2])):
        print('held',flush=True);sys.stdin.readline()
except ProjectLockError as exc:
    print(exc.reason,flush=True)
'''
    ps=[subprocess.Popen(child_program(code,tmp_path,json.dumps(options())),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
    try:
        for p in ps:p.stdin.write('go\n');p.stdin.flush()
        results=[p.stdout.readline().strip() for p in ps]
        assert sorted(results)==['held','project_lock_busy']
        winner=ps[results.index('held')];winner.stdin.write('release\n');winner.stdin.flush()
        for p in ps:assert p.wait()==0,p.stderr.read()
    finally:
        for p in ps:
            if p.poll() is None:p.terminate();p.wait()
            for stream in (p.stdin,p.stdout,p.stderr):stream.close()


def test_no_unsupported_platform_fallback_without_exclusive_kernel_lock(tmp_path):
    make_project(tmp_path);before=inventory(tmp_path)
    with patch('specroad.changes._lock_files.sys.platform','other'):
        with pytest.raises(ProjectLockError) as e:
            with project_lock(tmp_path,**options()):pytest.fail('entered')
    assert e.value.reason=='native_lock_unavailable' and inventory(tmp_path)==before


def test_proc_start_parser_handles_complex_process_name():
    raw=b'123 (name ) with (parentheses)\nand spaces) S '+ b'0 '*18 + b'789 0 0'
    assert _proc_stat(raw,123)==('linux-startticks:789','S')
    with pytest.raises(ValueError):_proc_stat(raw,124)


def test_inaccessible_proc_never_claims_dead_from_pid_number_alone():
    probe=LinuxOwnerProbe(); pid=9876
    good=b'%d (self) S '%os.getpid()+b'0 '*18+b'123'
    def read(path):
        if path=='/proc/self/stat':return good
        raise FileNotFoundError(path)
    with patch('specroad.changes._lock_process._read',read):
        with patch('specroad.changes._lock_process.os.kill',side_effect=PermissionError()):
            assert probe.process(pid)==('unknown',None)
        with patch('specroad.changes._lock_process.os.kill',return_value=None):
            assert probe.process(pid)==('unknown',None)
        with patch('specroad.changes._lock_process.os.kill',side_effect=ProcessLookupError()):
            assert probe.process(pid)==('absent',None)


def test_unknown_host_observation_stays_unknown_not_hostname_fallback():
    with patch('specroad.changes._lock_process._read',side_effect=PermissionError()):
        assert LinuxOwnerProbe().host_id() is None


def test_completed_lock_audit_does_not_block_existing_read_only_validation(tmp_path):
    record=stale(tmp_path);recover(tmp_path,record)
    make_project(tmp_path,artifact())
    before=inventory(tmp_path)
    with no_write_attempts():
        r=validate_project_read_only(tmp_path,profile_resources=profile_resources(),core_key='core@0.2.0')
    assert r.passed and inventory(tmp_path)==before


def test_portable_module_and_zipapp_contain_native_lock_api(tmp_path):
    from tests.support.portable import build_distribution
    built=build_distribution(tmp_path/'dist')
    # Query actual build products, not strings from documentation.
    # The builder returns locations, used by existing portable tests.
    assert built
    packages=list((tmp_path/'dist').rglob('specroad/__init__.py'))
    assert packages
    root=tmp_path/'project';root.mkdir();make_project(root)
    import sys
    code='''
import sys
sys.path.insert(0,sys.argv[1])
from specroad.changes import project_lock,inspect_project_lock,recover_project_lock
with project_lock(sys.argv[2],kind='writer',command='change apply',project_id='sample',transaction_id='t') as h:
    assert h.check()
assert inspect_project_lock(sys.argv[2]).data['owner_state']=='absent'
'''
    archive=list((tmp_path/'dist').rglob('*.pyz'))
    assert archive
    for path in (packages[0].parent.parent,archive[0]):
        run=subprocess.run([sys.executable,'-I','-B','-c',code,str(path),str(root)],capture_output=True,text=True)
        assert run.returncode==0,run.stderr


def test_corrupted_metadata_never_becomes_forceable_lock(tmp_path):
    record=stale(tmp_path)
    changes=[{'process_id':True},{'process_start_id':''},{'host_id':[]},
             {'lock_id':'00000000-0000-0000-0000-000000000000'},
             {'request_id':'invalid request'}, {'transaction_id':None},
             {'created_at':'2026-01-01T00:00:00+00:00'}, {'extra':True}]
    for values in changes:
        raw=canonical_json_bytes({**record.data,**values})
        put(tmp_path,'.specroad/locks/project.json',raw)
        before=inventory(tmp_path)
        with pytest.raises(ProjectLockError):
            recover(tmp_path,record,accept_remote_risk=True)
        assert inventory(tmp_path)==before


def test_partial_owner_write_stays_blocking_not_silently_repaired(tmp_path):
    make_project(tmp_path)
    real=os.write
    calls=[]
    def short(fd,buf):
        calls.append(True)
        if len(calls)==1:return real(fd,buf[:12])
        raise OSError(errno.ENOSPC,'full')
    with patch('specroad.changes._lock_files.os.write',short):
        with pytest.raises(OSError):
            with project_lock(tmp_path,**options()):pytest.fail('entered')
    path=tmp_path/'.specroad/locks/project.json'
    assert path.stat().st_size==12
    with pytest.raises(ProjectLockError):
        with project_lock(tmp_path,**options()):pytest.fail('entered')
    assert path.stat().st_size==12


def test_busy_native_recovery_never_creates_an_audit_file(tmp_path):
    record=stale(tmp_path)
    with LockFiles(tmp_path) as files:
        files.acquire();before=inventory(tmp_path)
        with pytest.raises(ProjectLockError) as error:
            recover(tmp_path,record,accept_remote_risk=True)
        assert error.value.reason=='project_lock_busy'
        assert inventory(tmp_path)==before


def test_supported_kernel_failure_has_no_best_effort_unlocked_path(tmp_path):
    import fcntl
    make_project(tmp_path);before=inventory(tmp_path)
    with patch.object(fcntl,'flock',side_effect=OSError(errno.ENOSYS,'unsupported')):
        with pytest.raises(ProjectLockError) as error:
            with project_lock(tmp_path,**options()):pytest.fail('entered')
    assert error.value.reason=='native_lock_unavailable' and inventory(tmp_path)==before


def test_status_rejects_changed_owner_during_observation(tmp_path):
    record=stale(tmp_path)
    class Changing(Probe):
        def process(self,pid):
            v={**record.data,'process_start_id':'other'}
            put(tmp_path,'.specroad/locks/project.json',canonical_json_bytes(v))
            return 'absent',None
    with pytest.raises(ProjectLockError) as error:
        inspect_project_lock(tmp_path,owner_probe=Changing('known-host'))
    assert error.value.reason=='lock_status_changed'


def test_removed_record_is_not_inferred_recovered_on_second_call(tmp_path):
    record=stale(tmp_path);recover(tmp_path,record);before=inventory(tmp_path)
    with pytest.raises(ProjectLockError) as error:recover(tmp_path,record)
    assert error.value.reason=='lock_record_missing' and inventory(tmp_path)==before
