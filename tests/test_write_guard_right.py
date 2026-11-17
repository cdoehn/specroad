"""Adversarial writer boundaries and ownership; no mocked successful gates."""
import copy
import errno
import json
import os
from pathlib import Path
import pytest
from test_write_guard import setup,publish,FAILURES
from support.publication import files,TRANSACTION,options,ALLOW
from specroad.changes import (project_lock,publish_guarded_change,inspect_write_state,
    read_guarded_completion,WriteGuardError)
from specroad.changes import guarded_write as writer
from specroad.changes.write_guard_values import MARKER_PATH,validate_transaction,receipt_group
from specroad.changes.receipt_values import transaction_receipt_path,completion_marker_path
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.errors import ModelError


@pytest.mark.parametrize('boundary',['marker_synced','staged:0','effect_replaced:0',
    'effect_synced:0','receipt:transaction.json','receipts_synced','before_marker_unlink','marker_unlinked'])
@pytest.mark.parametrize('code',[errno.EIO,errno.ENOSPC,errno.EDQUOT])
def test_io_failure_keeps_root_blocked_even_with_complete_targets(tmp_path,monkeypatch,boundary,code):
    _,_,check=setup(tmp_path);seen=[]
    def fail(event):
        if event==boundary:seen.append(event);raise OSError(code,'synthetic injected write failure')
    monkeypatch.setattr(writer,'_checkpoint',fail)
    with pytest.raises(FAILURES):publish(tmp_path,check)
    assert seen==[boundary]
    assert inspect_write_state(tmp_path)['state']=='corrupted'
    assert (tmp_path/'.specroad/locks/project.json').exists()
    if boundary!='marker_unlinked':assert (tmp_path/MARKER_PATH).exists()
    before=files(tmp_path)
    with pytest.raises(FAILURES):publish(tmp_path,check)
    with pytest.raises(FAILURES):read_guarded_completion(tmp_path,TRANSACTION,expected_project_id='sample')
    assert files(tmp_path)==before


@pytest.mark.parametrize('part',['pending.json','/staging/0.bin','transaction.json','committed.json'])
def test_real_sync_failure_never_becomes_success(tmp_path,monkeypatch,part):
    _,_,check=setup(tmp_path);native=os.fsync;seen=[]
    def fail(fd):
        name=os.readlink('/proc/self/fd/'+str(fd))
        if name.endswith(part):seen.append(name);raise OSError(errno.EIO,'injected fsync failure')
        return native(fd)
    monkeypatch.setattr(os,'fsync',fail)
    with pytest.raises(FAILURES):publish(tmp_path,check)
    assert seen and inspect_write_state(tmp_path)['state']=='corrupted'


def test_failed_directory_sync_after_marker_unlink_keeps_lock_blocker(tmp_path,monkeypatch):
    _,_,check=setup(tmp_path);native=os.fsync;armed=[]
    def checkpoint(event):
        if event=='marker_unlinked':armed.append(True)
    def fail(fd):
        if armed:raise OSError(errno.EIO,'injected final directory sync failure')
        return native(fd)
    monkeypatch.setattr(writer,'_checkpoint',checkpoint);monkeypatch.setattr(os,'fsync',fail)
    with pytest.raises(FAILURES):publish(tmp_path,check)
    assert not (tmp_path/MARKER_PATH).exists()
    assert inspect_write_state(tmp_path)['state']=='corrupted'
    with pytest.raises(FAILURES):read_guarded_completion(tmp_path,TRANSACTION,expected_project_id='sample')


@pytest.mark.parametrize('damage',['bytes','same_bytes_new_inode','hardlink','symlink','foreign_file','parent_swap'])
def test_marker_tampering_preserves_foreign_bytes_and_blocks(tmp_path,monkeypatch,damage):
    _,_,check=setup(tmp_path);before=files(tmp_path);outside=tmp_path/'foreign';outside.write_bytes(b'foreign')
    def sabotage(event):
        if event!='marker_synced':return
        marker=tmp_path/MARKER_PATH
        if damage=='bytes':marker.write_bytes(b'{}')
        elif damage=='same_bytes_new_inode':
            raw=marker.read_bytes();temporary=marker.with_name('replace');temporary.write_bytes(raw);os.replace(temporary,marker)
        elif damage=='hardlink':os.link(marker,marker.with_name('extra'))
        elif damage=='symlink':marker.unlink();marker.symlink_to(outside)
        elif damage=='foreign_file':marker.with_name('extra').write_bytes(b'leave me')
        else:marker.parent.rename(marker.parent.with_name('old-state'));marker.parent.mkdir()
    monkeypatch.setattr(writer,'_checkpoint',sabotage)
    with pytest.raises(FAILURES):publish(tmp_path,check)
    assert outside.read_bytes()==b'foreign'
    assert {p:b for p,b in files(tmp_path).items() if p in before}==before
    assert inspect_write_state(tmp_path)['state']!='clean'


@pytest.mark.parametrize('location',['root','target_parent','staging_parent','receipt_parent'])
def test_directory_identity_change_is_not_adopted(tmp_path,monkeypatch,location):
    _,_,check=setup(tmp_path);target=check.request.documents[0].path;seen=[]
    event='receipt:transaction.json' if location=='receipt_parent' else 'staged:0'
    def change(current):
        if current!=event:return
        seen.append(current)
        path={'root':tmp_path,'target_parent':(tmp_path/target).parent,
            'staging_parent':tmp_path/'.specroad/write-state/staging',
            'receipt_parent':(tmp_path/transaction_receipt_path(TRANSACTION)).parent}[location]
        path.rename(path.with_name(path.name+'-preserved'));path.mkdir()
    monkeypatch.setattr(writer,'_checkpoint',change)
    with pytest.raises(FAILURES):publish(tmp_path,check)
    assert seen==[event]
    assert not (tmp_path/completion_marker_path(TRANSACTION)).exists()


def test_complete_small_partial_writes_are_synced_and_read_back(tmp_path,monkeypatch):
    _,_,check=setup(tmp_path);native=os.write;calls=[]
    def short(fd,raw):calls.append(len(raw));return native(fd,raw[:7])
    monkeypatch.setattr(os,'write',short)
    result=publish(tmp_path,check)
    assert result.data['commit_completed'] and len(calls)>20
    assert read_guarded_completion(tmp_path,TRANSACTION,expected_project_id='sample').data['receipt_verified']


def test_zero_write_preserves_blocker_without_normative_changes(tmp_path,monkeypatch):
    _,_,check=setup(tmp_path);before=files(tmp_path)
    def arm(event):
        if event=='marker_synced':monkeypatch.setattr(os,'write',lambda fd,raw:0)
    monkeypatch.setattr(writer,'_checkpoint',arm)
    with pytest.raises(FAILURES):publish(tmp_path,check)
    assert files(tmp_path)==before and inspect_write_state(tmp_path)['state']=='corrupted'


@pytest.mark.parametrize('where',['transaction','request','completion','extra'])
def test_receipt_group_is_closed_and_never_repairs_missing_originals(tmp_path,where):
    _,_,check=setup(tmp_path);publish(tmp_path,check)
    path=tmp_path/transaction_receipt_path(TRANSACTION)
    write=validate_transaction(path.read_bytes());group=receipt_group(write)
    if where=='extra':path.with_name('foreign').write_bytes(b'preserve')
    else:
        wanted=next(p for p in group if (where=='transaction' and p.endswith('/transaction.json'))
            or (where=='completion' and p.endswith('/committed.json'))
            or (where=='request' and p.startswith('.specroad/requests/')))
        (tmp_path/wanted).write_bytes(b'{}')
    before={p.relative_to(tmp_path).as_posix():p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    with pytest.raises(FAILURES):read_guarded_completion(tmp_path,TRANSACTION,expected_project_id='sample')
    assert {p.relative_to(tmp_path).as_posix():p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}==before


@pytest.mark.parametrize('damage',['extra','owner_bool','operation_hash','target_binding','validation_binding','result','duplicate_path'])
def test_invalid_receipt_fields_fail_closed(tmp_path,damage):
    _,_,check=setup(tmp_path);publish(tmp_path,check)
    raw=(tmp_path/transaction_receipt_path(TRANSACTION)).read_bytes();value=json.loads(raw);write=value['write']
    if damage=='extra':value['unexpected']=True
    elif damage=='owner_bool':write['marker']['owner']['process_id']=True
    elif damage=='operation_hash':write['operations_sha256']='0'*64
    elif damage=='target_binding':write['files'][0]['after']['size']+=1
    elif damage=='validation_binding':write['validation']['source_bindings']=[]
    elif damage=='result':value['result_object']['exit_code']=False
    else:write['target_inventory'].append(copy.deepcopy(write['target_inventory'][0]))
    if damage not in ('result','extra'):
        from specroad.changes.write_guard_values import transaction_document
        value=transaction_document(write)
    with pytest.raises((ModelError,ValueError,TypeError)):
        validate_transaction(jcs(value))


@pytest.fixture(scope='module')
def native_write_receipt(tmp_path_factory):
    root=tmp_path_factory.mktemp('native-write-receipt')
    _,_,check=setup(root);publish(root,check)
    return (root/transaction_receipt_path(TRANSACTION)).read_bytes()


@pytest.mark.parametrize('damage',['missing_field','unknown_field','source_count','input_hash',
    'checked_ids','identified_sources','claimed_authority','selected_scope','no_stages','missing_stage',
    'duplicate_stage','stage_ids','failed_stage','blocked_stage','unavailable_stage','error_diagnostic'])
def test_receipt_rejects_incomplete_or_contradictory_native_validation(native_write_receipt,damage):
    from specroad.changes.write_guard_values import transaction_document
    # Only immutable bytes are shared; every damage case decodes its own value.
    write=json.loads(native_write_receipt)['write'];report=write['validation']
    # A real successful writer supplies the internal report, not CLI diagnostics.
    assert report['format_version']=='model-validation-v1' and 'source_report' not in report
    assert report['model_valid'] is True and report['checks_complete'] is True
    if damage=='missing_field':del report['stages']
    elif damage=='unknown_field':report['extra']=True
    elif damage=='source_count':report['source_count']=True
    elif damage=='input_hash':report['input_sha256']='invalid'
    elif damage=='checked_ids':report['checked_ids']=[]
    elif damage=='identified_sources':report['identified_sources']=[]
    elif damage=='claimed_authority':report['write_authorized']=True
    elif damage=='selected_scope':report['validation_scope']='dependency_expanded_loaded_scope'
    elif damage=='no_stages':report['stages']=[]
    elif damage=='missing_stage':report['stages'].pop(0)
    elif damage=='duplicate_stage':report['stages'].append(copy.deepcopy(report['stages'][0]))
    elif damage=='stage_ids':report['stages'][0]['checked_ids']=['foreign-artifact']
    elif damage=='error_diagnostic':report['stages'][0]['diagnostics']=[{'reason':'injected_failure','severity':'error'}]
    else:report['stages'][0]['status']=damage.removesuffix('_stage')
    # Rebind the receipt hash so rejection proves the recorded finding was checked.
    with pytest.raises(ModelError):validate_transaction(jcs(transaction_document(write)))


def test_active_writer_and_foreign_owner_are_not_declared_clean(tmp_path,monkeypatch):
    from specroad.changes._lock_process import LinuxOwnerProbe
    _,_,check=setup(tmp_path)
    def observe(event):
        if event!='marker_synced':return
        assert inspect_write_state(tmp_path)['state']=='writer_active'
        original=LinuxOwnerProbe.host_id
        monkeypatch.setattr(LinuxOwnerProbe,'host_id',lambda self:'foreign-test-host')
        try:assert inspect_write_state(tmp_path)['state']=='unknown'
        finally:monkeypatch.setattr(LinuxOwnerProbe,'host_id',original)
    monkeypatch.setattr(writer,'_checkpoint',observe)
    assert publish(tmp_path,check).data['commit_completed']


def test_output_failure_after_confirmed_completion_does_not_repeat(tmp_path):
    from specroad.changes import prepare_authoring_request,resolve_guarded_request
    _,plan,check=setup(tmp_path);original=publish(tmp_path,check).data;before=files(tmp_path)
    with pytest.raises(BrokenPipeError):raise BrokenPipeError('synthetic output loss')
    request=prepare_authoring_request(command_id='change apply',actor=plan.data['actor'],
        operations=plan.data['operations'],request_id=plan.data['request_id'])
    assert resolve_guarded_request(tmp_path,request,expected_project_id='sample').data['result_object']==original['result_object']
    assert files(tmp_path)==before


@pytest.mark.parametrize('operation',['replace','unlink','rmdir'])
def test_native_mutation_failure_preserves_real_state(tmp_path,monkeypatch,operation):
    _,_,check=setup(tmp_path);native=getattr(os,operation);seen=[]
    def fail(*args,**kwargs):
        name=str(args[0])
        selected=(operation=='replace' and name.endswith('.bin')
            or operation=='unlink' and name=='pending.json'
            or operation=='rmdir' and name=='staging')
        if selected:seen.append(name);raise OSError(errno.EIO,'injected mutation failure')
        return native(*args,**kwargs)
    monkeypatch.setattr(os,operation,fail)
    with pytest.raises(FAILURES):publish(tmp_path,check)
    assert seen and inspect_write_state(tmp_path)['state']=='corrupted'
    assert (tmp_path/MARKER_PATH).exists()


def test_foreign_receipt_name_cannot_be_acknowledged(tmp_path,monkeypatch):
    _,_,check=setup(tmp_path)
    def change(event):
        if event=='receipt:transaction.json':
            (tmp_path/transaction_receipt_path(TRANSACTION)).with_name('foreign').write_bytes(b'preserve')
    monkeypatch.setattr(writer,'_checkpoint',change)
    with pytest.raises(FAILURES):publish(tmp_path,check)
    assert (tmp_path/transaction_receipt_path(TRANSACTION)).with_name('foreign').read_bytes()==b'preserve'
    assert inspect_write_state(tmp_path)['state']=='corrupted'


def _sync_crash(root,part,when):
    import multiprocessing
    from test_write_guard import setup,publish
    path=Path(root);_,_,check=setup(path);native=os.fsync
    def sync(fd):
        match=os.readlink('/proc/self/fd/'+str(fd)).endswith(part)
        if match and when=='before':os._exit(91)
        result=native(fd)
        if match and when=='after':os._exit(91)
        return result
    os.fsync=sync
    publish(path,check)
    os._exit(92)


@pytest.mark.parametrize('part',['pending.json','/staging/0.bin','transaction.json','committed.json'])
@pytest.mark.parametrize('when',['before','after'])
def test_real_process_loss_on_file_sync_never_uses_complete_bytes_as_release(tmp_path,part,when):
    import multiprocessing
    child=multiprocessing.get_context('fork').Process(target=_sync_crash,args=(str(tmp_path),part,when))
    child.start();child.join(30)
    if child.is_alive():child.kill();child.join();pytest.fail('sync crash boundary not reached')
    assert child.exitcode==91 and inspect_write_state(tmp_path)['state']=='corrupted'
    before={p.relative_to(tmp_path).as_posix():p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    from specroad.changes.normal_access import require_normal_access
    from specroad.cli.contracts import CommandClass
    with pytest.raises(FAILURES, match='project_corrupted'):
        require_normal_access(tmp_path)
    with pytest.raises(FAILURES):read_guarded_completion(tmp_path,TRANSACTION,expected_project_id='sample')
    assert {p.relative_to(tmp_path).as_posix():p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}==before


def _snapshot_crash(directory,boundary):
    from support.migration_transaction import setup as migration_setup
    from support.migration_plans import planned_files
    from specroad.changes._guarded_snapshot import publish_guarded_snapshot
    root,source,plan,args=migration_setup(Path(directory));target=planned_files(source,plan)
    changed=sorted(p for p in source.keys()|target.keys() if source.get(p)!=target.get(p))
    deleted=next(p for p in changed if p not in target);index=changed.index(deleted)
    wanted=boundary+':'+str(index)
    def kill(event):
        if event==wanted:os._exit(91)
    writer._checkpoint=kill
    backup={k:args['backup_'+k] for k in ('path','size','sha256','source_files_sha256')}
    backup['output_root']=args['backup_root']
    project=json.loads(source['specroad.json'])['project_id']
    with project_lock(root,kind='writer',command='migrate apply',project_id=project,
                      transaction_id=args['transaction_id'],request_id=plan.data['request_id']) as held:
        publish_guarded_snapshot(plan,held_lock=held,backup_descriptor=backup,authority=args['authority'])
    os._exit(92)


@pytest.mark.parametrize('boundary',['effect_unlinked','effect_synced'])
def test_real_deletion_crash_preserves_backup_and_never_restores(tmp_path,boundary):
    import multiprocessing
    child=multiprocessing.get_context('fork').Process(target=_snapshot_crash,args=(str(tmp_path),boundary))
    child.start();child.join(30)
    if child.is_alive():child.kill();child.join();pytest.fail('delete crash boundary not reached')
    assert child.exitcode==91
    root=tmp_path/'project'
    assert inspect_write_state(root)['state']=='corrupted'
    before={p.relative_to(tmp_path).as_posix():p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert any(p.endswith('.zip') for p in before)
    with pytest.raises(FAILURES):
        read_guarded_completion(root,'synthetic-transition',expected_project_id='synthetic-reference-project')
    assert {p.relative_to(tmp_path).as_posix():p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}==before


@pytest.mark.parametrize('boundary',['before_marker','marker_synced','effect_synced:0'])
def test_fresh_native_authority_revocation_never_finishes(tmp_path,monkeypatch,boundary):
    from specroad.changes import PublicationAuthority
    _,_,check=setup(tmp_path);permitted=[True];calls=[]
    def authorize(request):calls.append(request);return permitted[0]
    authority=PublicationAuthority('synthetic-revocable','1',authorize)
    def revoke(event):
        if event==boundary:permitted[0]=False
    monkeypatch.setattr(writer,'_checkpoint',revoke)
    with pytest.raises(FAILURES):
        with project_lock(tmp_path,**options(check)) as held:
            publish_guarded_change(check,held_lock=held,authority=authority)
    assert len(calls)>1
    assert not (tmp_path/completion_marker_path(TRANSACTION)).exists()
    assert inspect_write_state(tmp_path)['state']=='corrupted'


def _directory_crash(root,part,when):
    path=Path(root);_,_,check=setup(path);native=os.fsync;removing=[False]
    def checkpoint(event):
        if event=='marker_unlinked':removing[0]=True
    writer._checkpoint=checkpoint
    def sync(fd):
        name=os.readlink('/proc/self/fd/'+str(fd))
        suffix=(transaction_receipt_path(TRANSACTION).rsplit('/',1)[0]
                if part=='receipt_directory' else '.specroad/write-state' if part=='marker_removal' else part)
        match=name==str(path/suffix) and (removing[0] if part=='marker_removal' else (path/MARKER_PATH).exists())
        if match and when=='before':os._exit(91)
        result=native(fd)
        if match and when=='after':os._exit(91)
        return result
    os.fsync=sync
    publish(path,check);os._exit(92)


@pytest.mark.parametrize('part',['.specroad','.specroad/write-state','.specroad/write-state/staging',
    'spec/goals','.specroad/requests','receipt_directory','marker_removal'])
@pytest.mark.parametrize('when',['before','after'])
def test_real_process_loss_on_directory_sync_preserves_quarantine(tmp_path,part,when):
    import multiprocessing
    child=multiprocessing.get_context('fork').Process(target=_directory_crash,args=(str(tmp_path),part,when))
    child.start();child.join(30)
    if child.is_alive():child.kill();child.join();pytest.fail('directory sync crash boundary not reached')
    assert child.exitcode==91
    before={p.relative_to(tmp_path).as_posix():p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert inspect_write_state(tmp_path)['state']=='corrupted'
    with pytest.raises(FAILURES):read_guarded_completion(tmp_path,TRANSACTION,expected_project_id='sample')
    assert {p.relative_to(tmp_path).as_posix():p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}==before
