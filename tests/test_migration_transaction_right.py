"""Real file-prefix crashes, explicit native recovery and shared request history."""
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import pytest
from tests.support.migration_transaction import setup, apply, normative, journal_path
from tests.support.migration_plans import ACTOR, planned_files
from specroad.changes.schema_transition_values import SchemaTransitionError, TransitionJournal
from specroad.changes.locking import project_lock
from specroad.changes.recovery_values import RecoveryAuthority
from specroad.changes.recovery import (discard_unpublished_transaction,
    rollback_interrupted_transaction, complete_published_transaction, inspect_recovery)
from specroad.changes.receipt_values import transaction_receipt_path, request_receipt_path
from specroad.storage.operational_preflight import observe_operational_preflight
from specroad.security import ProjectBoundary
from specroad.model.errors import ModelError
from specroad.changes.execution_values import ChangeExecutionError
from specroad.security import SafetyViolation

FAILURES=(ModelError,ChangeExecutionError,SafetyViolation,OSError)


def tree(root):
    return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}


def current_journal(root,args):
    path=journal_path(root,args)
    if not path.exists():path=(root/transaction_receipt_path(args['transaction_id'])).with_name('journal.json')
    if not path.exists():
        path=root/'.specroad/recovery/transaction-audit'/('schema-'+sha256(args['transaction_id'].encode()).hexdigest())/'journal.json'
    return TransitionJournal(path.read_bytes())


def interrupt(root,plan,args,monkeypatch,event):
    from specroad.changes import schema_transition as writer
    seen=[]
    def fail(name):
        if name==event:
            seen.append(name)
            raise OSError('Synthetic durability interruption')
    with monkeypatch.context() as patch:
        patch.setattr(writer,'_checkpoint',fail)
        with pytest.raises(SchemaTransitionError) as caught:apply(root,plan,args)
    assert seen==[event] and caught.value.write_state=='unknown'
    return current_journal(root,args)


def recover(root,args,*,action=None,authority=None,expected=None):
    journal=current_journal(root,args);state=journal.data['state']
    if action is None:
        status=inspect_recovery(root,transaction_id=args['transaction_id']).data['transactions'][0]
        action='complete' if status['complete_target_verified'] else 'discard' if state in ('building','prepared') else 'rollback'
    authority=authority or RecoveryAuthority('synthetic-host','1',lambda request:True)
    with project_lock(root,kind='recovery',command='recover run',project_id=journal.data['project_id'],
            transaction_id=args['transaction_id'],request_id=journal.data['request_id']) as held:
        common=dict(held_lock=held,authority=authority,expected_journal_sha256=expected or journal.sha256)
        if action=='discard':
            return discard_unpublished_transaction(None,args['transaction_id'],actor=ACTOR,
                reason='Synthetic explicit crash recovery',**common).data
        fn=complete_published_transaction if action=='complete' else rollback_interrupted_transaction
        return fn(args['transaction_id'],**common).data


@pytest.mark.parametrize('point',['journal:building:0','image:source.zip','journal:prepared:0','journal:committing:0'])
def test_unpublished_crashes_restore_exact_source_and_keep_evidence(tmp_path,monkeypatch,point):
    root,source,plan,args=setup(tmp_path)
    interrupt(root,plan,args,monkeypatch,point)
    assert normative(root)==source
    observation=inspect_recovery(root,transaction_id=args['transaction_id']).data
    assert observation['normal_access_blocked'] and observation['transactions'][0]['base_verified']
    assert not observation['transactions'][0]['permitted_actions']
    result=recover(root,args)
    assert result['current_source_verified'] and result['cleanup_completed']
    assert normative(root)==source and not journal_path(root,args).exists()
    archived=current_journal(root,args)
    assert archived.data['state']=='rolled_back'
    assert list((root/'.specroad/recovery/transaction-audit').rglob('recovery-*.json'))
    assert not (root/request_receipt_path(plan.data['request_id'])).exists()
    assert observe_operational_preflight(ProjectBoundary(root))['consistency_state']=='consistent'


# This literal synthetic fixture has thirteen native file effects. Collection
# only declares cases; planning/backups and all I/O run inside each Apply test.
FILE_CHANGE_INDICES = tuple(range(13))
FILE_CRASH_CASES = tuple((kind, index) for kind in ('effect', 'ack')
                        for index in FILE_CHANGE_INDICES)


@pytest.mark.parametrize(('kind', 'index'), FILE_CRASH_CASES,
                         ids=[f'{kind}-{index:02d}' for kind, index in FILE_CRASH_CASES])
def test_every_file_effect_and_ack_crash_has_one_proven_outcome(tmp_path,monkeypatch,kind,index):
    root,source,plan,args=setup(tmp_path)
    changes=plan.data['operations'][0]['changes'];total=len(changes)
    # Fail if the real plan gains/loses a position; never silently sample it.
    assert tuple(range(total))==FILE_CHANGE_INDICES
    event='effect:'+str(index) if kind=='effect' else 'journal:committing:'+str(index+1)
    interrupt(root,plan,args,monkeypatch,event)
    assert observe_operational_preflight(ProjectBoundary(root))['consistency_state']!='consistent'
    status=inspect_recovery(root,transaction_id=args['transaction_id']).data['transactions'][0]
    assert status['published_count']==index+1
    assert status['recorded_published_count']==index+(kind=='ack')
    assert status['critical_inputs_verified']
    with pytest.raises(FAILURES):apply(root,plan,args)
    # The status was already observed above. Real recovery still requalifies
    # its inputs under the native lock; only a duplicate helper read disappears.
    complete=index+1==total
    outcome=recover(root,args,action='complete' if complete else 'rollback')
    expected=planned_files(source,plan) if complete else source
    assert normative(root)==expected
    assert outcome['cleanup_completed'] and not journal_path(root,args).exists()
    assert current_journal(root,args).data['state']==('committed' if complete else 'rolled_back')


@pytest.mark.parametrize('point',['committed','receipts','archived'])
def test_late_crash_completes_without_repeating_target_writes(tmp_path,monkeypatch,point):
    root,source,plan,args=setup(tmp_path);total=len(plan.data['operations'][0]['changes'])
    event='journal:committed:'+str(total) if point=='committed' else point
    interrupt(root,plan,args,monkeypatch,event)
    expected=normative(root);inodes={p:(root/p).stat().st_ino for p in expected}
    result=recover(root,args,action='complete')
    assert result['normative_writes_by_recovery']==0 and result['recovery_completed']
    assert normative(root)==expected==planned_files(source,plan)
    assert {p:(root/p).stat().st_ino for p in expected}==inodes
    replay=apply(root,plan,args)
    assert replay['replayed'] and not replay['current_target_verified']


def test_original_request_replays_historical_result_after_later_edit(tmp_path):
    root,source,plan,args=setup(tmp_path);first=apply(root,plan,args)
    path=root/'spec/requirements/SR-REQ-0001.json';value=json.loads(path.read_bytes())
    value['revision']+=1;value['title']='Later ordinary project edit'
    path.write_text(json.dumps(value));before=tree(root)
    # Replay needs durable original proof, not a still-existing external ZIP.
    Path(args['backup_path']).unlink()
    replay=apply(root,plan,args)
    assert replay['replayed'] and not replay['current_target_verified']
    for name in ('published_paths','target_model_root_sha256','transaction_id','request_id'):
        assert replay[name]==first[name]
    assert tree(root)==before
    from specroad.changes.receipt_read import read_transaction_completion
    from specroad.storage.project import ProjectSource
    observation=read_transaction_completion(ProjectSource(root),args['transaction_id']).data
    assert observation['receipt_verified'] and not observation['current_target_verified']


def test_new_request_at_target_is_noop_without_revision_or_receipt(tmp_path):
    a=tmp_path/'a';a.mkdir();root,source,plan,args=setup(a);apply(root,plan,args)
    b=tmp_path/'b';b.mkdir();_,_,other,options=setup(b,fields={'request_id':'synthetic:second'})
    before=tree(root);result=apply(root,other,options)
    assert result['status']=='not_required' and result['no_change']
    assert result['write_state']=='not_committed' and not result['current_target_verified']
    assert tree(root)==before


def test_request_conflict_uses_shared_normative_namespace(tmp_path):
    a=tmp_path/'a';a.mkdir();root,source,plan,args=setup(a);apply(root,plan,args)
    b=tmp_path/'b';b.mkdir();_,_,other,options=setup(b,fields={'planned_at':'2026-11-04T03:00:00Z'})
    before=tree(root)
    with pytest.raises(FAILURES) as seen:apply(root,other,options)
    assert seen.value.reason=='request_operations_conflict'
    assert tree(root)==before
    from specroad.changes.receipt_read import _read_confirmed_request
    from specroad.storage.project import ProjectSource
    receipt=_read_confirmed_request(ProjectSource(root),plan.data['request_id'])
    assert receipt.data['operations_sha256']
    assert receipt.data['format_version']=='schema-transition-request-receipt-v1'
    from specroad.changes.receipt_values import RequestReceipt
    from specroad.model.canonical import canonical_json_bytes
    legacy=receipt.data;legacy['format_version']='request-receipt-v1'
    with pytest.raises(FAILURES):RequestReceipt(canonical_json_bytes(legacy))


@pytest.mark.parametrize('tamper',['journal','transaction','request','source','image','root'])
def test_historical_proof_cannot_be_forged_or_copied(tmp_path,tamper):
    root,source,plan,args=setup(tmp_path);apply(root,plan,args)
    receipt=root/transaction_receipt_path(args['transaction_id']);archive=receipt.parent
    if tamper=='root':
        clone=tmp_path/'clone';shutil.copytree(root,clone);root=clone
    else:
        path={'journal':archive/'journal.json','transaction':receipt,
              'request':root/request_receipt_path(plan.data['request_id']),
              'source':archive/'source.zip','image':next((archive/'staging').glob('*.bin'))}[tamper]
        path.write_bytes(path.read_bytes()+b'!')
    before=tree(root)
    with pytest.raises(FAILURES):apply(root,plan,args)
    assert tree(root)==before


@pytest.mark.parametrize('tamper',['before','staging','source','backup','unrelated','third_value','mode','journal','unknown_work',
                                  'pending_count','pending_bytes','pending_name'])
def test_recovery_rejects_unproven_bytes_without_normative_writes(tmp_path,monkeypatch,tamper):
    root,source,plan,args=setup(tmp_path)
    journal=interrupt(root,plan,args,monkeypatch,'effect:0');work=journal_path(root,args).parent
    if tamper in ('before','staging'):p=next((work/tamper).glob('*.bin'));p.write_bytes(p.read_bytes()+b'!')
    elif tamper=='source':(work/'source.zip').write_bytes(b'broken')
    elif tamper=='backup':Path(args['backup_path']).write_bytes(b'broken')
    elif tamper=='unrelated':(root/'unexpected.txt').write_bytes(b'foreign')
    elif tamper=='third_value':(root/plan.data['operations'][0]['changes'][0]['path']).write_bytes(b'third')
    elif tamper=='mode':(root/'specroad.json').chmod(0o600)
    elif tamper=='journal':journal_path(root,args).write_bytes(journal_path(root,args).read_bytes()+b' ')
    elif tamper.startswith('pending_'):
        from specroad.model.canonical import canonical_json_bytes
        value=journal.data
        value.update(state='rolling_back',published_count=2 if tamper=='pending_count' else 1)
        raw=canonical_json_bytes(value)
        token='0'*64 if tamper=='pending_name' else sha256(raw).hexdigest()
        pending=work/('journal.'+token+'.pending')
        pending.write_bytes(raw+b'!' if tamper=='pending_bytes' else raw)
    else:(work/'unknown.txt').write_bytes(b'foreign evidence')
    before=normative(root)
    with pytest.raises(FAILURES) as caught:recover(root,args,action='rollback')
    if tamper.startswith('pending_'):
        assert caught.value.reason=='transition_pending_journal_changed'
        assert pending.read_bytes()==(raw+b'!' if tamper=='pending_bytes' else raw)
        assert journal_path(root,args).read_bytes()==journal.source_bytes
    assert normative(root)==before and journal_path(root,args).exists()


@pytest.mark.parametrize('length',[0,19,None])
def test_recovery_resumes_partial_initial_rollback_marker(tmp_path,monkeypatch,length):
    from specroad.changes import _schema_transition_io as io
    from specroad.changes.recovery_values import RecoveryError
    root,source,plan,args=setup(tmp_path)
    journal=interrupt(root,plan,args,monkeypatch,'effect:2')
    before=normative(root);seen=[];write_new=io.write_new
    def interrupted_write(files,path,raw):
        if path.endswith('.pending'):
            value=json.loads(raw)
            if value['state']=='rolling_back' and value['published_count']==3:
                seen.append((path,raw))
                write_new(files,path,raw if length is None else raw[:length])
                raise OSError('Synthetic interrupted rollback marker write')
        return write_new(files,path,raw)
    with monkeypatch.context() as patch:
        patch.setattr(io,'write_new',interrupted_write)
        with pytest.raises(RecoveryError):recover(root,args,action='rollback')
    assert len(seen)==1 and normative(root)==before
    assert journal_path(root,args).read_bytes()==journal.source_bytes
    path,raw=seen[0]
    assert (root/path).read_bytes()==(raw if length is None else raw[:length])
    observation=inspect_recovery(root,transaction_id=args['transaction_id']).data['transactions'][0]
    assert observation['published_count']==3 and observation['recorded_published_count']==2
    assert observation['critical_inputs_verified']
    outcome=recover(root,args,action='rollback')
    assert outcome['current_source_verified'] and outcome['cleanup_completed']
    assert normative(root)==source and not journal_path(root,args).exists()
    assert current_journal(root,args).data['state']=='rolled_back'


@pytest.mark.parametrize('denial',['false','nonbool','mutated_request','mutated_backup','stale_hash'])
def test_recovery_requires_fresh_bound_host_authority(tmp_path,monkeypatch,denial):
    root,source,plan,args=setup(tmp_path);interrupt(root,plan,args,monkeypatch,'effect:0')
    before=normative(root)
    def authorize(request):
        if denial=='false':return False
        if denial=='nonbool':return 1
        if denial=='mutated_request':request['action']='complete'
        if denial=='mutated_backup':Path(args['backup_path']).write_bytes(b'changed')
        return True
    with pytest.raises(FAILURES):
        recover(root,args,action='rollback',authority=RecoveryAuthority('synthetic-host','1',authorize),
                expected='0'*64 if denial=='stale_hash' else None)
    assert normative(root)==before


def test_recovery_reentry_after_lost_rollback_effect(tmp_path,monkeypatch):
    from specroad.changes import schema_transition as writer
    root,source,plan,args=setup(tmp_path);interrupt(root,plan,args,monkeypatch,'effect:2')
    with monkeypatch.context() as patch:
        def fail(event):
            if event=='rollback:2':raise OSError('Synthetic lost rollback acknowledgement')
        patch.setattr(writer,'_checkpoint',fail)
        with pytest.raises(FAILURES):recover(root,args,action='rollback')
    assert current_journal(root,args).data['state']=='rolling_back'
    outcome=recover(root,args,action='rollback')
    assert outcome['current_source_verified'] and normative(root)==source
    before=tree(root);again=recover(root,args,action='rollback')
    assert again['normative_writes_by_recovery']==0 and tree(root)==before
    # Recovery retained new passive audit bytes. The original plan/backup no
    # longer bind the complete source, even though normative bytes are restored.
    with pytest.raises(SchemaTransitionError) as stale:apply(root,plan,args)
    assert stale.value.reason=='transition_source_changed' and stale.value.exit_code==6
    assert tree(root)==before and not journal_path(root,args).exists()

    # Prove the independent ID-reuse boundary with genuinely current inputs.
    # No audit is removed, source gate bypassed or product function replaced.
    from specroad.migration.planning import plan_migration
    from specroad.migration.backup import create_source_backup
    from specroad.migration.plan_values import file_bindings
    from specroad.bundles.migration_source import verify_source_backup
    from specroad.model.canonical import canonical_json_sha256
    from tests.support.migration_transaction import execution_inputs
    from tests.support.migration_plans import FIELDS
    fresh=plan_migration(before,inputs=execution_inputs(before),
        **{**FIELDS,'change_plan_id':'CP-synthetic-after-recovery',
           'request_id':'synthetic:after-recovery'})
    assert fresh.ready
    fresh_plan=fresh.change_plan;op=fresh_plan.data['operations'][0]
    assert op['source_files']==file_bindings(before)
    passive={p:raw for p,raw in before.items() if p.startswith('.specroad/')}
    assert passive and set(passive)<=set(op['protected_paths'])
    file_hash=canonical_json_sha256(file_bindings(before))
    backup=create_source_backup(root,output='after-recovery.zip',output_root=args['backup_root'],
        expected_source_files_sha256=file_hash)
    backup_raw=Path(backup['file']['path']).read_bytes()
    assert verify_source_backup(backup_raw,expected_sha256=backup['file']['sha256'],
        expected_source_files_sha256=file_hash).files==before
    current={**args,'expected_plan_sha256':fresh_plan.sha256,
        'expected_inputs_sha256':op['inputs_sha256'],
        'backup_path':backup['file']['path'],'backup_sha256':backup['file']['sha256'],
        'backup_size':backup['file']['size'],'backup_source_files_sha256':file_hash}
    with pytest.raises(SchemaTransitionError) as collision:apply(root,fresh_plan,current)
    assert collision.value.reason=='transition_id_collision' and collision.value.exit_code==6
    assert tree(root)==before and not journal_path(root,current).exists()
    assert Path(current['backup_path']).read_bytes()==backup_raw

    # A fresh transaction ID can use those same proved inputs and must retain
    # the complete original rollback audit while publishing the exact target.
    current['transaction_id']='synthetic-after-recovery'
    result=apply(root,fresh_plan,current)
    assert result['current_target_verified'] and result['write_state']=='committed'
    expected=planned_files(before,fresh_plan)
    assert normative(root)=={p:raw for p,raw in expected.items() if not p.startswith('.specroad/')}
    assert all((root/p).read_bytes()==raw for p,raw in passive.items())
    assert Path(current['backup_path']).read_bytes()==backup_raw


def test_discard_reentry_after_partial_build_and_terminal_failure(tmp_path,monkeypatch):
    from specroad.changes import schema_transition as writer
    root,source,plan,args=setup(tmp_path);interrupt(root,plan,args,monkeypatch,'journal:building:0')
    (journal_path(root,args).parent/'source.zip').write_bytes(Path(args['backup_path']).read_bytes()[:23])
    with monkeypatch.context() as patch:
        def fail(event):
            if event=='journal:rolling_back:0':raise OSError('Synthetic interrupted discard')
        patch.setattr(writer,'_checkpoint',fail)
        with pytest.raises(FAILURES):recover(root,args,action='discard')
    assert not current_journal(root,args).data['images_prepared']
    outcome=recover(root,args,action='rollback')
    assert outcome['current_source_verified'] and normative(root)==source


def test_partial_owned_move_is_preserved_during_rollback(tmp_path,monkeypatch):
    root,source,plan,args=setup(tmp_path);interrupt(root,plan,args,monkeypatch,'journal:committing:0')
    from specroad.migration.plan_values import unb64
    row=plan.data['operations'][0]['changes'][0];raw=unb64(row['after_bytes_base64'])
    token=sha256((row['path']+':'+sha256(raw).hexdigest()).encode()).hexdigest()+'.bin'
    path=journal_path(root,args).parent/'moves'/token;path.parent.mkdir();path.write_bytes(raw[:11])
    result=recover(root,args,action='rollback')
    assert result['current_source_verified'] and normative(root)==source
    assert list((root/'.specroad/recovery/transaction-audit').rglob(token))[0].read_bytes()==raw[:11]


@pytest.mark.parametrize('fault',['rename_after','unlink_after','fsync_after'])
def test_actual_io_failure_keeps_recoverable_file_prefix(tmp_path,monkeypatch,fault):
    root,source,plan,args=setup(tmp_path)
    from specroad.changes import _publication_io as publication, schema_transition as writer
    from specroad.authoring import _bootstrap_io as native
    original_rename=native._rename_native;original_unlink=os.unlink;original_fsync=os.fsync
    entered=False;failed=[]
    def checkpoint(event):
        nonlocal entered
        if event=='journal:committing:0':entered=True
    def rename(*a,**kw):
        result=original_rename(*a,**kw)
        if entered and fault=='rename_after' and not failed:
            failed.append(True);raise OSError('Synthetic lost rename response')
        return result
    def unlink(*a,**kw):
        result=original_unlink(*a,**kw)
        if entered and fault=='unlink_after' and a[0]=='core-reference01.json' and not failed:
            failed.append(True);raise OSError('Synthetic lost unlink response')
        return result
    def fsync(fd):
        result=original_fsync(fd)
        if entered and fault=='fsync_after' and not failed:
            failed.append(True);raise OSError('Synthetic lost fsync response')
        return result
    with monkeypatch.context() as patch:
        patch.setattr(writer,'_checkpoint',checkpoint);patch.setattr(native,'_rename_native',rename)
        patch.setattr(os,'unlink',unlink);patch.setattr(os,'fsync',fsync)
        with pytest.raises(FAILURES):apply(root,plan,args)
    assert failed
    outcome=recover(root,args)
    assert outcome['cleanup_completed']
    assert normative(root) in (source,planned_files(source,plan))
    assert all(p.stat().st_nlink==1 for p in root.rglob('*') if p.is_file())


@pytest.mark.skipif(not hasattr(os,'fork'),reason='Native Linux owner takeover uses fork')
@pytest.mark.parametrize('point',['effect:0','archived'])
def test_actual_dead_writer_uses_shared_owner_takeover(tmp_path,point):
    from specroad.changes import schema_transition as writer
    from specroad.changes.locking import inspect_project_lock
    from specroad.changes.recovery_lock import transaction_recovery_lock
    root,source,plan,args=setup(tmp_path)
    pid=os.fork()
    if pid==0:
        def checkpoint(event):
            if event==point:os._exit(73)
        writer._checkpoint=checkpoint
        try:apply(root,plan,args)
        except BaseException:os._exit(74)
        os._exit(75)
    _,status=os.waitpid(pid,0)
    assert os.waitstatus_to_exitcode(status)==73
    journal=current_journal(root,args);owner=inspect_project_lock(root).data
    assert owner['owner_state']=='dead'
    authority=RecoveryAuthority('synthetic-host','1',lambda request:True)
    with transaction_recovery_lock(root,args['transaction_id'],project_id=journal.data['project_id'],
            request_id=plan.data['request_id'],expected_lock_sha256=owner['record_sha256'],
            expected_journal_sha256=journal.sha256,authority=authority,actor=ACTOR,
            reason='Synthetic verified dead writer',force=True) as held:
        action=complete_published_transaction if point=='archived' else rollback_interrupted_transaction
        result=action(args['transaction_id'],held_lock=held,authority=authority,
            expected_journal_sha256=journal.sha256).data
    assert result['recovery_completed']
    assert normative(root)==(planned_files(source,plan) if point=='archived' else source)
    assert list((root/'.specroad/recovery/transaction-audit').rglob('completed.json'))
