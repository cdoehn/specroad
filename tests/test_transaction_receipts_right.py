"""Lost completion output and late cleanup failures never repeat a model write."""
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
from unittest.mock import patch
import pytest
from specroad.changes import (TransactionReceipt, RequestReceipt, CommittedJournal,
    ReceiptError, PublicationAuthority, read_transaction_completion,
    cleanup_completed_transaction, prepare_completion_receipts, completion_marker_path)
from specroad.model.canonical import canonical_json_bytes
from specroad.storage.project import ProjectSource
from support.receipts import published, finish
from support.publication import ALLOW, TRANSACTION, files
from support.folds import goal, edit, add_relation
from support.processes import run_core, run_python
from support.portable import build_distribution
from support.read_only import no_write_attempts


def load(root, preflight=None):
    return read_transaction_completion(ProjectSource(root),TRANSACTION,preflight=preflight)


def clean(f,h):
    return cleanup_completed_transaction(f,TRANSACTION,held_lock=h,authority=ALLOW)


def raw_inventory(root):
    return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_read_requires_committed_not_merely_persisted_receipts(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        t,r,c=prepare_completion_receipts(f,j)
        for record in (t,r):
            q=tmp_path/record.path;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(record.source_bytes)
        with pytest.raises(ReceiptError):load(tmp_path,f)
        assert (tmp_path/j.path).read_bytes()==j.source_bytes


def test_read_completed_proof_is_write_free_and_needs_no_lock(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        finish(f,h,j)
    before=raw_inventory(tmp_path)
    with no_write_attempts():
        result=load(tmp_path,f)
    assert result.data['commit_completed'] and result.data['current_target_verified']
    assert raw_inventory(tmp_path)==before
    assert not list((tmp_path/'.specroad/locks').iterdir())


def test_historical_completion_does_not_claim_current_target(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):finish(f,h,j)
    q=tmp_path/f.request.documents[0].path;q.write_bytes(q.read_bytes()+b' ')
    old=load(tmp_path)
    assert old.data['commit_completed'] and not old.data['current_target_verified']
    with pytest.raises(ReceiptError):load(tmp_path,f)


def test_lost_journal_rename_response_recovers_from_disk_without_write(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        baseline=files(tmp_path);native=os.replace
        def lose(*args,**kwargs):
            native(*args,**kwargs);raise OSError('lost acknowledgement')
        with patch.object(os,'replace',lose):
            with pytest.raises(ReceiptError) as error:finish(f,h,j)
        assert error.value.committed_possible
        assert load(tmp_path,f).data['commit_completed']
        assert files(tmp_path)==baseline
        with pytest.raises(ReceiptError):finish(f,h,j)
        assert files(tmp_path)==baseline


@pytest.mark.parametrize('failure',range(1,11))
def test_each_completion_fsync_failure_preserves_evidence_and_never_rewrites_model(tmp_path,failure):
    with published(tmp_path) as (m,p,f,h,j):
        before=files(tmp_path);native=os.fsync;calls=0
        def failing(fd):
            nonlocal calls
            calls+=1
            if calls==failure:raise OSError('sync failure')
            return native(fd)
        with patch.object(os,'fsync',failing):
            with pytest.raises(ReceiptError) as error:finish(f,h,j)
        assert calls==failure
        assert error.value.mutation_possible
        assert files(tmp_path)==before
        state=json.loads((tmp_path/j.path).read_bytes())['state']
        if state=='committed':
            assert error.value.committed_possible and load(tmp_path,f).data['commit_completed']
        else:
            assert state=='committing'
            with pytest.raises(ReceiptError):load(tmp_path,f)
        assert (tmp_path/j.path).exists()


def test_short_writes_finish_receipts_completely(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        native=os.write
        with patch.object(os,'write',lambda fd,data:native(fd,data[:37])):
            result=finish(f,h,j)
        assert result.data['commit_completed'] and load(tmp_path,f).data['receipt_verified']


def test_zero_byte_write_leaves_recovery_not_completion(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        before=files(tmp_path)
        with patch.object(os,'write',return_value=0):
            with pytest.raises(ReceiptError):finish(f,h,j)
        assert files(tmp_path)==before
        assert (tmp_path/j.path).read_bytes()==j.source_bytes
        with pytest.raises(ReceiptError):load(tmp_path,f)


def test_no_space_during_receipt_write_keeps_partial_file(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        t,r,c=prepare_completion_receipts(f,j);native=os.write;calls=0
        def full(fd,data):
            nonlocal calls
            calls+=1
            if calls>1:raise OSError(28,'full')
            return native(fd,data[:17])
        with patch.object(os,'write',full):
            with pytest.raises(ReceiptError):finish(f,h,j)
        assert (tmp_path/t.path).stat().st_size==17
        assert (tmp_path/j.path).read_bytes()==j.source_bytes
        assert not (tmp_path/r.path).exists()


def test_cleanup_archives_marker_before_discard_and_preserves_receipts(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        result=finish(f,h,j);t,r,c=prepare_completion_receipts(f,j)
        norm=files(tmp_path);native=os.unlink;removed=[]
        def remove(name,**kwargs):
            assert (tmp_path/completion_marker_path(TRANSACTION)).read_bytes()==c.source_bytes
            assert (tmp_path/t.path).read_bytes()==t.source_bytes
            assert (tmp_path/r.path).read_bytes()==r.source_bytes
            removed.append(name);return native(name,**kwargs)
        with patch.object(os,'unlink',remove):done=clean(f,h)
        assert done.data['commit_completed'] and done.data['cleanup_completed']
        assert removed[-1]=='journal.json'
        assert not (tmp_path/j.path).parent.exists()
        assert files(tmp_path)==norm
        assert load(tmp_path,f).data['cleanup_completed']
        assert h._files.journal_entries()==()
        assert clean(f,h).data['cleanup_completed']


def test_no_request_receipt_cleanup_still_preserves_transaction(tmp_path):
    with published(tmp_path,request_id=None) as (m,p,f,h,j):
        finish(f,h,j);assert clean(f,h).data['cleanup_completed']
        value=load(tmp_path,f).data
        assert value['receipts']['request'] is None
        assert not (tmp_path/'.specroad/requests').exists()


def test_late_unlink_failure_returns_committed_but_incomplete_cleanup(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        finish(f,h,j);before=files(tmp_path)
        with patch.object(os,'unlink',side_effect=OSError('denied')):
            result=clean(f,h)
        assert result.data['commit_completed'] and not result.data['cleanup_completed']
        assert result.data['warnings'] and files(tmp_path)==before
        assert (tmp_path/j.path).exists()
        assert clean(f,h).data['cleanup_completed']
        assert files(tmp_path)==before


def test_lost_cleanup_unlink_response_resumes_only_cleanup(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        finish(f,h,j);before=files(tmp_path);native=os.unlink;calls=0
        def lose(name,**kwargs):
            nonlocal calls
            calls+=1;native(name,**kwargs)
            raise OSError('lost unlink result')
        with patch.object(os,'unlink',lose):result=clean(f,h)
        assert calls==1 and result.data['commit_completed'] and not result.data['cleanup_completed']
        with patch.object(os,'replace',side_effect=AssertionError('no repeat writer')):
            done=clean(f,h)
        assert done.data['cleanup_completed'] and files(tmp_path)==before


def test_cleanup_fsync_failure_after_deletion_does_not_undo_commit(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        finish(f,h,j);native=os.unlink;sync=os.fsync;deleted=False
        def remove(*a,**kw):
            nonlocal deleted
            result=native(*a,**kw);deleted=True;return result
        def fail(fd):
            if deleted:raise OSError('late directory sync')
            return sync(fd)
        with patch.object(os,'unlink',remove),patch.object(os,'fsync',fail):result=clean(f,h)
        assert result.data['commit_completed'] and not result.data['cleanup_completed']
        assert load(tmp_path).data['receipt_verified']
        assert clean(f,h).data['cleanup_completed']


def test_foreign_work_is_not_deleted_or_silently_ignored(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        finish(f,h,j);foreign=(tmp_path/j.path).parent/'unknown';foreign.write_bytes(b'keep')
        with pytest.raises(ReceiptError):clean(f,h)
        assert foreign.read_bytes()==b'keep'
        assert load(tmp_path).data['commit_completed']
        assert not (tmp_path/completion_marker_path(TRANSACTION)).exists()


def test_foreign_image_is_never_deleted(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        finish(f,h,j);foreign=(tmp_path/j.path).parent/'before'/'unknown';foreign.write_bytes(b'keep')
        with pytest.raises(ReceiptError):clean(f,h)
        assert foreign.read_bytes()==b'keep' and (tmp_path/j.path).exists()


def test_tampered_before_image_blocks_cleanup_not_historical_proof(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        finish(f,h,j);q=tmp_path/j.data['files'][0]['before_image_path'];old=q.read_bytes()
        q.write_bytes(b'X'+old[1:])
        with pytest.raises(ReceiptError):clean(f,h)
        assert q.exists() and load(tmp_path).data['commit_completed']


def test_no_cleanup_before_committed_even_with_receipts(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        t,r,c=prepare_completion_receipts(f,j)
        for value in (t,r):
            q=tmp_path/value.path;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(value.source_bytes)
        before=raw_inventory(tmp_path)
        with pytest.raises(ReceiptError):clean(f,h)
        assert raw_inventory(tmp_path)==before


def test_denied_cleanup_authority_does_not_discard_anything(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        finish(f,h,j);before=raw_inventory(tmp_path)
        with pytest.raises(ReceiptError) as e:
            cleanup_completed_transaction(f,TRANSACTION,held_lock=h,
                authority=PublicationAuthority('no','1',lambda r:False))
        assert e.value.exit_code==7 and raw_inventory(tmp_path)==before


def test_cleanup_after_target_change_is_refused_without_deletion(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        finish(f,h,j);q=tmp_path/f.request.documents[0].path;q.write_bytes(q.read_bytes()+b' ')
        before=raw_inventory(tmp_path)
        with pytest.raises(ReceiptError):clean(f,h)
        assert raw_inventory(tmp_path)==before
        assert load(tmp_path).data['commit_completed']


def test_missing_receipt_rejects_committed_flag(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        result=finish(f,h,j);(tmp_path/result.data['receipts']['request']['path']).unlink()
        with pytest.raises(ReceiptError):load(tmp_path,f)
        with pytest.raises(ReceiptError):clean(f,h)
        assert (tmp_path/j.path).exists()


def test_same_size_restored_timestamp_receipt_tamper_is_detected(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        result=finish(f,h,j);q=tmp_path/result.data['receipts']['transaction']['path'];stat=q.stat()
        data=q.read_bytes();assert b'planner' in data
        q.write_bytes(data.replace(b'planner',b'plannex'));os.utime(q,ns=(stat.st_atime_ns,stat.st_mtime_ns))
        with pytest.raises(ReceiptError):load(tmp_path,f)


@pytest.mark.parametrize('kind',['symlink','hardlink','fifo'])
def test_receipt_special_files_refused_without_hanging(tmp_path,kind):
    with published(tmp_path) as (m,p,f,h,j):
        result=finish(f,h,j);q=tmp_path/result.data['receipts']['request']['path']
        original=q.read_bytes();outside=tmp_path.parent/(tmp_path.name+'-outside');outside.write_bytes(original);q.unlink()
        if kind=='symlink':q.symlink_to(outside)
        elif kind=='hardlink':os.link(outside,q)
        else:os.mkfifo(q)
        with pytest.raises(ReceiptError):load(tmp_path,f)
        assert outside.read_bytes()==original


def test_relocated_copy_is_not_original_project_identity(tmp_path):
    root=tmp_path/'source';root.mkdir()
    with published(root) as (m,p,f,h,j):finish(f,h,j)
    copy=tmp_path/'copy';shutil.copytree(root,copy)
    with pytest.raises(ReceiptError):load(copy)


def test_truncated_archived_marker_is_not_repaired(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        finish(f,h,j);path=tmp_path/completion_marker_path(TRANSACTION);path.write_bytes(b'{')
        before=raw_inventory(tmp_path)
        with pytest.raises(ReceiptError):load(tmp_path)
        with pytest.raises(ReceiptError):clean(f,h)
        assert before==raw_inventory(tmp_path)


def test_success_output_without_marker_is_not_completion(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        assert 'state' in j.data
        (tmp_path/'.specroad/cache').mkdir(exist_ok=True)
        (tmp_path/'.specroad/cache/output.txt').write_text('LOCAL APPLY: SUCCESS')
        with pytest.raises(ReceiptError):load(tmp_path,f)


def test_receipt_result_rejects_boolean_zero_and_fabricated_created_ids(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        t,r,c=prepare_completion_receipts(f,j)
        for value,kind in ((t,TransactionReceipt),(r,RequestReceipt)):
            data=value.data;data['result_object']['exit_code']=False
            with pytest.raises(ReceiptError):kind(canonical_json_bytes(data))
        data=t.data;data['created_ids']=['fiction'];data['result_object']['created_ids']=['fiction']
        with pytest.raises(ReceiptError):TransactionReceipt(canonical_json_bytes(data))


def test_receipt_retains_ordered_operations_and_created_relation_ids(tmp_path):
    a,b=goal(1),goal(2);op=add_relation(a,b,13)
    with published(tmp_path,artifacts=[a,b],operations=[edit(a,'a'),op]) as (m,p,f,h,j):
        result=finish(f,h,j);t=TransactionReceipt((tmp_path/result.data['receipts']['transaction']['path']).read_bytes())
        assert t.data['operations']==p.data['operations']
        assert t.data['created_ids']==[op['relation']['relation_id']]


def test_mutation_during_final_authority_is_caught_before_receipts(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        def mutate(request):
            q=tmp_path/f.request.documents[0].path;q.write_bytes(q.read_bytes()+b' ');return True
        with pytest.raises(ReceiptError):finish(f,h,j,authority=PublicationAuthority('m','1',mutate))
        assert not (tmp_path/'.specroad/transactions/receipts').exists()


def test_receipt_replacement_between_writes_blocks_committed(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        t,r,c=prepare_completion_receipts(f,j);native=os.fsync;done=False
        def replace(fd):
            nonlocal done
            native(fd)
            if not done and os.readlink('/proc/self/fd/'+str(fd))==str(tmp_path/r.path):
                q=tmp_path/t.path;other=q.with_name('swap');other.write_bytes(q.read_bytes());os.replace(other,q);done=True
        with patch.object(os,'fsync',replace):
            with pytest.raises(ReceiptError):finish(f,h,j)
        assert done and json.loads((tmp_path/j.path).read_bytes())['state']=='committing'


def test_foreign_receipt_directory_entry_prevents_reuse(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        t,r,c=prepare_completion_receipts(f,j);foreign=(tmp_path/t.path).parent/'committed.json'
        foreign.parent.mkdir(parents=True);foreign.write_bytes(b'foreign')
        with pytest.raises(ReceiptError):finish(f,h,j)
        assert foreign.read_bytes()==b'foreign' and not (tmp_path/t.path).exists()


def test_commit_and_cleanup_receipts_remain_independent_data(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        finish(f,h,j);clean(f,h)
        result=load(tmp_path,f);raw=result.data;raw['receipts'].clear()
        assert result.data['receipts']['transaction'] and not result.data['write_authorized']
        assert not result.data['idempotency_guaranteed']
        with pytest.raises(TypeError):bool(result)


def test_real_process_exit_after_commit_reconstructs_success(tmp_path):
    root=tmp_path/'p';root.mkdir()
    body=f'''import sys,os
sys.path.insert(0,{str(Path(__file__).parent.resolve())!r})
from pathlib import Path
from support.receipts import published,finish
root=Path({str(root)!r})
with published(root) as (m,p,f,h,j):
 finish(f,h,j)
 os._exit(41)
'''
    result=run_core(body,tmp_path,capture=True)
    assert result.returncode==41,result.stderr
    recovered=load(root)
    assert recovered.data['commit_completed'] and recovered.data['cleanup_required']
    assert (root/'.specroad/locks/project.json').exists() # not silently recovered here


def test_inherited_lock_cannot_finalize_or_clean(tmp_path):
    body=f'''import sys,os
sys.path.insert(0,{str(Path(__file__).parent.resolve())!r})
from pathlib import Path
from support.receipts import published,finish
from specroad.changes import ReceiptError
with published(Path({str(tmp_path)!r})) as (m,p,f,h,j):
 pid=os.fork()
 if pid==0:
  try:finish(f,h,j)
  except ReceiptError:os._exit(0)
  except BaseException:os._exit(3)
  os._exit(2)
 _,status=os.waitpid(pid,0)
 assert os.waitstatus_to_exitcode(status)==0
 assert h.check()
 assert not (Path({str(tmp_path)!r})/'.specroad/transactions/receipts').exists()
'''
    result=run_core(body,tmp_path,capture=True)
    assert result.returncode==0,result.stderr


def test_many_completed_files_are_bound_and_cleaned_without_truncation(tmp_path):
    artifacts=[goal(i) for i in range(1,34)]
    with published(tmp_path,artifacts=artifacts,operations=[edit(a,'changed') for a in artifacts]) as (m,p,f,h,j):
        result=finish(f,h,j);t=TransactionReceipt((tmp_path/result.data['receipts']['transaction']['path']).read_bytes())
        assert len(t.data['result_object']['published_paths'])==33
        baseline=files(tmp_path);assert clean(f,h).data['cleanup_completed']
        assert files(tmp_path)==baseline and load(tmp_path,f).data['receipt_verified']


def test_module_and_zipapp_receipt_completion_and_cleanup_are_portable(tmp_path):
    products=build_distribution(tmp_path/'distribution')
    for i,original in enumerate(products):
        moved=tmp_path/('moved-'+str(i)+('.pyz' if original.suffix=='.pyz' else ''));original.rename(moved)
        root=tmp_path/('p-'+str(i));root.mkdir()
        body=f'''import sys
sys.path[:0]=[{str(moved)!r},{str(Path(__file__).parent.resolve())!r}]
from pathlib import Path
from support.receipts import published,finish
from support.publication import ALLOW,TRANSACTION
from specroad.changes import read_transaction_completion,cleanup_completed_transaction
from specroad.storage.project import ProjectSource
root=Path({str(root)!r})
with published(root) as (m,p,f,h,j):
 assert finish(f,h,j).data['commit_completed']
 assert cleanup_completed_transaction(f,TRANSACTION,held_lock=h,authority=ALLOW).data['cleanup_completed']
 assert read_transaction_completion(ProjectSource(root),TRANSACTION,preflight=f).data['current_target_verified']
'''
        result=run_python(['-I','-S','-B','-c',body],tmp_path,capture=True)
        assert result.returncode==0,result.stderr


@pytest.mark.parametrize('failure',range(1,8))
def test_each_cleanup_sync_failure_keeps_commit_proven(tmp_path,failure):
    with published(tmp_path) as (m,p,f,h,j):
        finish(f,h,j);before=files(tmp_path);native=os.fsync;calls=0
        def fail(fd):
            nonlocal calls
            calls+=1
            if calls==failure:raise OSError('cleanup sync')
            return native(fd)
        with patch.object(os,'fsync',fail):result=clean(f,h)
        assert calls==failure
        assert result.data['commit_completed'] and not result.data['cleanup_completed']
        assert result.data['warnings'] and files(tmp_path)==before
        assert clean(f,h).data['cleanup_completed']
        assert files(tmp_path)==before


def test_lost_final_directory_removal_response_retains_archival_proof(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        finish(f,h,j);native=os.rmdir;before=files(tmp_path)
        def lost(name,**kw):
            result=native(name,**kw)
            if name==TRANSACTION:raise OSError('lost cleanup reply')
            return result
        with patch.object(os,'rmdir',lost):result=clean(f,h)
        assert result.data['commit_completed'] and not result.data['cleanup_completed']
        assert not (tmp_path/j.path).parent.exists()
        assert load(tmp_path,f).data['receipt_verified']
        assert clean(f,h).data['cleanup_completed'] and files(tmp_path)==before


def test_receipt_only_without_any_committed_marker_cannot_restore_completion(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        finish(f,h,j);clean(f,h)
        (tmp_path/completion_marker_path(TRANSACTION)).unlink()
        with pytest.raises(ReceiptError):load(tmp_path)


def test_changed_receipt_during_readback_invalidates_observation(tmp_path):
    from specroad.changes import receipt_read as reader
    with published(tmp_path) as (m,p,f,h,j):
        result=finish(f,h,j);q=tmp_path/result.data['receipts']['request']['path']
        original=reader._read;calls=0
        def altering(directory,name,**kwargs):
            nonlocal calls
            data=original(directory,name,**kwargs)
            if name==q.name:
                calls+=1
                if calls==1:q.write_bytes(data+b' ')
            return data
        with patch.object(reader,'_read',altering):
            with pytest.raises(ReceiptError):load(tmp_path)
        assert calls>=1


def test_foreign_work_appearing_during_cleanup_is_preserved(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        finish(f,h,j);native=os.unlink;foreign=(tmp_path/j.path).parent/'unexpected'
        def add(name,**kwargs):
            r=native(name,**kwargs);foreign.write_bytes(b'keep');return r
        with patch.object(os,'unlink',add):result=clean(f,h)
        assert result.data['commit_completed'] and not result.data['cleanup_completed']
        assert foreign.read_bytes()==b'keep' and (tmp_path/j.path).exists()


def test_authority_changing_receipt_prevents_cleanup(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        result=finish(f,h,j);q=tmp_path/result.data['receipts']['transaction']['path']
        def bad(request):q.write_bytes(q.read_bytes()+b' ');return True
        with pytest.raises(ReceiptError):
            cleanup_completed_transaction(f,TRANSACTION,held_lock=h,
                authority=PublicationAuthority('bad','1',bad))
        assert (tmp_path/j.path).exists()
        assert not (tmp_path/completion_marker_path(TRANSACTION)).exists()


def test_original_request_must_match_when_rechecking_current_completion(tmp_path):
    from specroad.changes import (prepare_publication_check,project_lock,
        begin_building_journal,stage_building_journal,CommittingJournal)
    from support.publication import prepared,options
    from support.committing import publish
    from support.targets import plan,POLICY
    m,p,f=prepared(tmp_path)
    different=plan(m,p.data['operations'],request_id='different')
    other=prepare_publication_check(different,m,policy=POLICY)
    with project_lock(tmp_path,**options(f)) as h:
        j=begin_building_journal(f,held_lock=h,transaction_id=TRANSACTION,authority=ALLOW)
        ready=stage_building_journal(f,j,held_lock=h,authority=ALLOW)
        publish(f,ready,h)
        journal=CommittingJournal((tmp_path/j.path).read_bytes())
        finish(f,h,journal)
        with pytest.raises(ReceiptError):load(tmp_path,other)
        assert load(tmp_path,f).data['current_target_verified']


def test_new_reader_inputs_are_explicit_and_not_converted(tmp_path):
    class Foreign:
        def __str__(self):raise AssertionError('no conversion')
    with pytest.raises(ReceiptError):read_transaction_completion(Foreign(),TRANSACTION)
    with published(tmp_path) as (m,p,f,h,j):
        finish(f,h,j)
        with pytest.raises(ReceiptError):read_transaction_completion(ProjectSource(tmp_path),Foreign())
        with pytest.raises(ReceiptError):load(tmp_path,Foreign())


def test_unknown_result_fields_and_unsafe_output_paths_fail_closed(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        t,r,c=prepare_completion_receipts(f,j)
        data=r.data;data['result_object']['pretend']=True
        with pytest.raises(ReceiptError):RequestReceipt(canonical_json_bytes(data))
        data=r.data;data['result_object']['published_paths']=['../unsafe']
        with pytest.raises(ReceiptError):RequestReceipt(canonical_json_bytes(data))
