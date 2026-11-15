"""Native complete writes and real crash boundaries; synthetic test authority."""
import json
import multiprocessing
import os
from pathlib import Path
import pytest
from support.publication import prepared, options, ALLOW, TRANSACTION, files
from support.targets import plan as make_plan, POLICY, ACTOR, TIME
from specroad.changes import (project_lock,prepare_publication_check,publish_guarded_change,
    read_guarded_completion,inspect_write_state,WriteGuardError)
from specroad.changes import guarded_write as writer
from specroad.changes.write_guard_values import MARKER_PATH,validate_transaction
from specroad.changes.receipt_values import transaction_receipt_path,request_receipt_path
from specroad.model.errors import ModelError
from specroad.security import SafetyViolation

FAILURES=(ModelError,SafetyViolation,OSError)


def setup(root,**kw):
    model,original,_=prepared(root,**kw)
    plan=make_plan(model,original.data['operations'],request_id='write-guard-request')
    return model,plan,prepare_publication_check(plan,model,policy=POLICY)


def publish(root,check):
    with project_lock(root,**options(check)) as held:
        return publish_guarded_change(check,held_lock=held,authority=ALLOW)


def test_complete_write_and_read_only_retry_preserve_exact_effect(tmp_path):
    _,plan,check=setup(tmp_path)
    result=publish(tmp_path,check).data
    assert result['commit_completed'] and result['current_target_verified']
    assert not (tmp_path/MARKER_PATH).exists()
    raw=(tmp_path/transaction_receipt_path(TRANSACTION)).read_bytes();write=validate_transaction(raw)
    assert write['marker']['plan_sha256']==plan.sha256
    assert write['files'] and all(set(row)=={'path','before','after'} for row in write['files'])
    assert inspect_write_state(tmp_path)['state']=='clean'
    before={p.relative_to(tmp_path).as_posix():p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    retry=read_guarded_completion(tmp_path,TRANSACTION,expected_project_id='sample').data
    assert retry['result_object']==result['result_object'] and retry['replayed']
    assert not retry['current_target_verified']
    assert {p.relative_to(tmp_path).as_posix():p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}==before


def test_full_create_and_replace_share_the_native_writer(tmp_path):
    from support.folds import goal, edit, create
    original=goal()
    # Use the existing checked creation helper, never raw filesystem publication.
    model,_,_=prepared(tmp_path)
    fresh=goal(2, revision=1, created_at=TIME, updated_at=TIME,
        created_by=ACTOR, updated_by=ACTOR)
    operations=[edit(model.artifacts[0],'Changed'),create(fresh)]
    selected=make_plan(model,operations,request_id='two-effects')
    check=prepare_publication_check(selected,model,policy=POLICY)
    result=publish(tmp_path,check)
    assert len(result.data['result_object']['published_paths'])==2
    assert {d.path:d.content for d in check.request.documents}.items()<=files(tmp_path).items()


def _crash(root,event):
    from support.folds import goal,create,edit
    model,_,_=setup(Path(root))
    plan=make_plan(model,[edit(model.artifacts[0],'Changed'),create(goal(2, revision=1, created_at=TIME, updated_at=TIME,
        created_by=ACTOR, updated_by=ACTOR))],request_id='write-guard-request')
    check=prepare_publication_check(plan,model,policy=POLICY)
    def kill(current):
        if current==event:os._exit(91)
    writer._checkpoint=kill
    publish(Path(root),check)
    os._exit(92)


@pytest.mark.parametrize('event',['before_marker','marker_synced','staged:0','effect_replaced:0',
    'effect_synced:0','effect_replaced:1','effect_synced:1','receipt:transaction.json','receipts_synced','before_marker_unlink','marker_unlinked'])
def test_process_loss_never_replays_or_unlocks_partial_write(tmp_path,event):
    ctx=multiprocessing.get_context('fork')
    child=ctx.Process(target=_crash,args=(str(tmp_path),event));child.start();child.join(20)
    if child.is_alive():child.kill();child.join();pytest.fail('native crash test did not reach its boundary')
    assert child.exitcode==91
    observed=inspect_write_state(tmp_path,expected_project_id='sample')
    assert observed['state']=='corrupted' and observed['manual_git_restore_required']
    before={p.relative_to(tmp_path).as_posix():p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    with pytest.raises(FAILURES):read_guarded_completion(tmp_path,TRANSACTION,expected_project_id='sample')
    assert {p.relative_to(tmp_path).as_posix():p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}==before
    if event=='before_marker':assert not (tmp_path/MARKER_PATH).exists()
    elif event!='marker_unlinked':assert (tmp_path/MARKER_PATH).exists()


def test_incomplete_receipt_blocks_success(tmp_path):
    _,_,check=setup(tmp_path);publish(tmp_path,check)
    (tmp_path/request_receipt_path('write-guard-request')).unlink()
    with pytest.raises(FAILURES):read_guarded_completion(tmp_path,TRANSACTION,expected_project_id='sample')


def test_existing_marker_and_old_transaction_never_authorize_new_write(tmp_path):
    _,_,check=setup(tmp_path)
    path=tmp_path/MARKER_PATH;path.parent.mkdir(parents=True);path.write_bytes(b'{}')
    original=files(tmp_path)
    with pytest.raises(FAILURES):publish(tmp_path,check)
    assert files(tmp_path)==original and path.read_bytes()==b'{}'


def test_native_snapshot_create_replace_delete_uses_same_guard(tmp_path):
    from support.migration_transaction import setup as migration_setup,normative
    from support.migration_plans import planned_files
    from specroad.changes._guarded_snapshot import publish_guarded_snapshot
    root,source,plan,args=migration_setup(tmp_path)
    target=planned_files(source,plan)
    assert source.keys()-target.keys(), 'native migration fixture must contain a real deletion'
    backup={k:args['backup_'+k] for k in ('path','size','sha256','source_files_sha256')}
    backup['output_root']=args['backup_root']
    from specroad.storage.json_syntax import parse_json_object
    project_id=parse_json_object(source['specroad.json'])['project_id']
    with project_lock(root,kind='writer',command='migrate apply',project_id=project_id,
                      transaction_id=args['transaction_id'],request_id=plan.data['request_id']) as held:
        result=publish_guarded_snapshot(plan,held_lock=held,backup_descriptor=backup,authority=args['authority'])
    assert result.data['commit_completed'] and normative(root)==target
    write=validate_transaction((root/transaction_receipt_path(args['transaction_id'])).read_bytes())
    assert any(row['after'] is None for row in write['files'])
    assert not (root/MARKER_PATH).exists()


def test_request_retry_returns_original_and_rejects_changed_intent(tmp_path):
    from specroad.changes import prepare_authoring_request,resolve_guarded_request
    from support.folds import edit
    model,plan,check=setup(tmp_path);original=publish(tmp_path,check).data
    def request(ops):return prepare_authoring_request(command_id='change apply',operations=ops,
        actor=plan.data['actor'],request_id=plan.data['request_id'])
    before=files(tmp_path)
    retry=resolve_guarded_request(tmp_path,request(plan.data['operations']),expected_project_id='sample')
    assert retry.data['result_object']==original['result_object']
    with pytest.raises(WriteGuardError,match='write_request_conflict'):
        resolve_guarded_request(tmp_path,request([edit(model.artifacts[0],'Different')]),expected_project_id='sample')
    assert files(tmp_path)==before
