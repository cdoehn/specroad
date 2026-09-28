"""Real final-boundary checks and normative effects, not diagnostic wording."""
from dataclasses import FrozenInstanceError, replace
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import json
import os
import pytest
from specroad.changes import (prepare_publication_check, recheck_publication,
    publish_after_recheck, PublicationCheckError, PublicationAuthority,
    PublicationPreflight, PublicationRecheck, project_lock, apply_change_plan)
from specroad.model.canonical import canonical_json_sha256
from support.publication import prepared, options, invoke, files, ALLOW, TRANSACTION, NativeGuardStorage
from support.targets import POLICY, plan, resign, gate
from support.folds import goal, edit, create


def test_preflight_reads_without_lock_or_writes(tmp_path):
    m,p,check=prepared(tmp_path);before=files(tmp_path)
    with patch.object(Path,'write_bytes',side_effect=AssertionError('write')), \
         patch.object(Path,'mkdir',side_effect=AssertionError('mkdir')):
        other=prepare_publication_check(p,m,policy=POLICY)
    assert files(tmp_path)==before and not (tmp_path/'.specroad').exists()
    assert check.data==other.data and check.data['final_check_required'] is True
    assert check.data['write_authorized'] is False and check.data['project_lock_acquired'] is False


def test_unmodified_base_invokes_exact_request_once_under_writer_lock(tmp_path):
    m,p,c=prepared(tmp_path);seen=[]
    with project_lock(tmp_path,**options(c)) as held:
        result=invoke(c,held,lambda r:seen.append((r.sha256,held.check())) or 17)
        assert result==17 and seen==[(c.request.sha256,True)] and held.check()
    assert json.loads((tmp_path/m.documents[0].path).read_bytes())['statement']!= 'Changed'


def test_existing_change_apply_can_use_native_last_guard(tmp_path):
    m,p,c=prepared(tmp_path);store=NativeGuardStorage(m,c)
    result=apply_change_plan(p,m,policy=POLICY,backend=store.backend)
    assert result.write_state=='committed' and len(store.calls)==1
    value=json.loads((tmp_path/m.documents[0].path).read_bytes())
    assert value['statement']=='Changed' and value['revision']==m.artifacts[0]['revision']+1
    assert not (tmp_path/'.specroad/locks/project.json').exists()


def test_last_report_is_observation_not_durable_write_proof(tmp_path):
    m,p,c=prepared(tmp_path);before=files(tmp_path)
    with project_lock(tmp_path,**options(c)) as held:
        r=recheck_publication(c,c.request,held_lock=held,transaction_id=TRANSACTION,authority=ALLOW)
        v=r.data
        assert v['ready_for_backend'] is True and v['normative_writes']==0
        assert v['preflight_reused_as_proof'] is False and v['write_authorized'] is False
        assert v['durability_verified'] is False and files(tmp_path)==before
        v['ready_for_backend']=False;assert r.data['ready_for_backend'] is True
        with pytest.raises(TypeError):bool(r)


@pytest.mark.parametrize('path_index',[0,1,2])
def test_source_changed_after_preflight_refuses_before_publication(tmp_path,path_index):
    m,p,c=prepared(tmp_path);path=tmp_path/sorted(m.source_files)[path_index]
    raw=path.read_bytes();path.write_bytes(raw+b' ');before=files(tmp_path);seen=[]
    with project_lock(tmp_path,**options(c)) as held:
        with pytest.raises(PublicationCheckError) as e:invoke(c,held,lambda r:seen.append(r))
        assert e.value.exit_code==6
    assert seen==[] and files(tmp_path)==before


def test_expected_revision_is_not_rebased(tmp_path):
    m,p,c=prepared(tmp_path)
    bad=resign(p,lambda v:v['operations'][0].update(expected_revision=999))
    with pytest.raises(Exception):prepare_publication_check(bad,m,policy=POLICY)
    assert not (tmp_path/'.specroad').exists()


def test_new_normative_json_after_plan_invalidates_inventory(tmp_path):
    m,p,c=prepared(tmp_path);f=tmp_path/'rules/unexpected.json';f.parent.mkdir();f.write_text('{}');seen=[]
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:seen.append(r))
    assert e.value.reason=='publication_inventory_changed' and seen==[]


def test_new_unmanaged_file_does_not_change_publication_inputs(tmp_path):
    m,p,c=prepared(tmp_path);(tmp_path/'notes.txt').write_text('not normative')
    with project_lock(tmp_path,**options(c)) as h:assert invoke(c,h,lambda r:True)


def test_deleted_source_is_conflict_not_empty_model(tmp_path):
    m,p,c=prepared(tmp_path);(tmp_path/m.documents[0].path).unlink();seen=[]
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:seen.append(r))
    assert e.value.exit_code==6 and seen==[]


def test_same_size_and_reset_mtime_do_not_hide_byte_change(tmp_path):
    m,p,c=prepared(tmp_path);path=tmp_path/m.documents[0].path;i=path.stat()
    raw=path.read_bytes();data=raw.replace(b'Sample',b'SamplE');assert raw!=data
    path.write_bytes(data);os.utime(path,ns=(i.st_atime_ns,i.st_mtime_ns))
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:True)
    assert e.value.exit_code==6


def test_identical_bytes_replaced_inode_is_conflict(tmp_path):
    m,p,c=prepared(tmp_path);path=tmp_path/m.documents[0].path
    other=path.with_suffix('.tmp');other.write_bytes(path.read_bytes());other.replace(path)
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:True)
    assert e.value.reason=='publication_footprint_changed'


def test_expired_lock_cannot_be_reused(tmp_path):
    m,p,c=prepared(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:pass
    with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:True)
    assert e.value.reason=='lock_handle_not_active'


@pytest.mark.parametrize('changed',[
    {'transaction_id':'wrong'}, {'request_id':'wrong'},
    {'command':'artifact update'}, {'kind':'recovery','command':'recover run'}])
def test_other_lock_request_never_authorizes_publication(tmp_path,changed):
    m,p,c=prepared(tmp_path);opts={**options(c),**changed}
    if changed.get('command')=='artifact update':opts['command']='update'
    # Writer command set is read from the product's declared contract.
    if changed.get('command')=='artifact update':
        from specroad.changes._lock_kinds import COMMANDS,LockKind
        opts['command']=next(x for x in COMMANDS[LockKind.WRITER] if x!='change apply')
    with project_lock(tmp_path,**opts) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:True)
    assert e.value.exit_code==6


def test_recovery_entry_appears_after_lock_stops_writer(tmp_path):
    m,p,c=prepared(tmp_path);seen=[]
    with project_lock(tmp_path,**options(c)) as h:
        journal=tmp_path/'.specroad/transactions/pending';journal.mkdir(parents=True)
        try:
            with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:seen.append(r))
            assert e.value.reason=='publication_recovery_required' and seen==[]
        finally:journal.rmdir()


@pytest.mark.parametrize('value',[False,None,1,'true',{},[]])
def test_authority_must_explicitly_allow_before_callback(tmp_path,value):
    m,p,c=prepared(tmp_path);seen=[]
    authority=PublicationAuthority('test','1',lambda r:value)
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:seen.append(r),authority=authority)
    assert e.value.exit_code==7 and seen==[]


def test_mutation_during_authorization_is_caught_after_callback(tmp_path):
    m,p,c=prepared(tmp_path);path=tmp_path/m.documents[0].path;seen=[]
    def authorize(r):path.write_bytes(path.read_bytes()+b' ');return True
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:
            invoke(c,h,lambda r:seen.append(r),authority=PublicationAuthority('change','1',authorize))
    assert e.value.exit_code==6 and seen==[]


def test_receipt_free_empty_plan_still_needs_fresh_native_check(tmp_path):
    m,p,c=prepared(tmp_path,operations=[])
    with project_lock(tmp_path,**options(c)) as h:
        assert invoke(c,h,lambda r:tuple(r.data['changed_paths']))==()


def test_check_does_not_mutate_input_objects(tmp_path):
    m,p,c=prepared(tmp_path);before=(m.source_files,p.source_bytes,c.request._encoded)
    with project_lock(tmp_path,**options(c)) as h:invoke(c,h,lambda r:None)
    assert (m.source_files,p.source_bytes,c.request._encoded)==before
    request=c.request;object.__setattr__(request,'_encoded',b'{}')
    assert c.request._encoded==before[2]
    with pytest.raises(TypeError):bool(c)


def test_preflight_and_final_observation_cannot_be_constructed_from_json():
    for cls in (PublicationPreflight,PublicationRecheck):
        with pytest.raises(TypeError):cls({'ready':True})


def test_changed_request_never_reaches_publisher(tmp_path):
    m,p,c=prepared(tmp_path);r=c.request;object.__setattr__(r,'documents',())
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:
            publish_after_recheck(c,r,held_lock=h,transaction_id=TRANSACTION,authority=ALLOW,publish=lambda r:True)
    assert e.value.reason=='publication_request_changed'


def test_publisher_failure_after_write_is_unknown_without_retry(tmp_path):
    m,p,c=prepared(tmp_path);seen=[];path=tmp_path/m.documents[0].path
    def action(r):seen.append(r);path.write_bytes(r.documents[0].content);raise OSError('after effect')
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,action)
    assert e.value.write_state=='unknown' and len(seen)==1
    assert json.loads(path.read_bytes())['statement']=='Changed'


def test_second_invocation_cannot_reuse_early_success_after_first_write(tmp_path):
    m,p,c=prepared(tmp_path);path=tmp_path/m.documents[0].path
    with project_lock(tmp_path,**options(c)) as h:
        invoke(c,h,lambda r:path.write_bytes(r.documents[0].content))
        with pytest.raises(PublicationCheckError):invoke(c,h,lambda r:True)
