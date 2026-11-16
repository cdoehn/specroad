"""18.v: real native migration and merge share the non-repairable guard."""
import json
from pathlib import Path
import pytest
from specroad.changes import schema_transition
from specroad.changes.schema_transition_values import SchemaTransitionError
from specroad.changes.write_guard_values import validate_transaction
from specroad.changes.snapshot_write_values import check_write
from specroad.changes.receipt_values import transaction_receipt_path, request_receipt_path
from specroad.changes.lock_values import ProjectLockError
from specroad.changes.execution_values import ChangeExecutionError
from specroad.model.errors import ModelError
from specroad.security import SafetyViolation
from support.read_only import inventory,no_write_attempts

FAILURES=(ModelError,ChangeExecutionError,ProjectLockError,SafetyViolation,OSError)


def scenario(tmp_path,kind):
    if kind=='migration':
        from support.migration_transaction import setup,apply
        from support.migration_plans import planned_files
        root,source,plan,args=setup(tmp_path)
        target=planned_files(source,plan)
    else:
        from test_merge_publication_right import multiple
        from support.merge_publication import apply,normative
        root,plan,args,qualified=multiple(tmp_path)
        source=normative(root);target=qualified.files
    return root,source,plan,args,target,apply


@pytest.mark.parametrize('kind',['migration','merge'])
def test_complete_publication_has_only_normal_proof_and_read_only_repeat(tmp_path,kind):
    root,source,plan,args,target,apply=scenario(tmp_path,kind)
    result=apply(root,plan,args)
    assert result['write_state']=='committed' and result['current_target_verified']
    receipt=root/transaction_receipt_path(args['transaction_id'])
    write=validate_transaction(receipt.read_bytes())
    assert check_write(write).source_bytes==plan.source_bytes
    assert write['validation']['backup']==result['backup']
    assert all((root/p).read_bytes()==raw for p,raw in target.items())
    assert set(p.name for p in receipt.parent.iterdir())=={'transaction.json','committed.json'}
    assert not (root/'.specroad/write-state/pending.json').exists()
    assert not (root/'.specroad/locks/project.json').exists()
    before=inventory(root)
    with no_write_attempts():repeat=apply(root,plan,args)
    assert repeat['replayed'] and not repeat['current_target_verified']
    assert not repeat['approval_granted'] and inventory(root)==before


@pytest.mark.parametrize('kind',['migration','merge'])
@pytest.mark.parametrize('point',['marker_synced','staged:0','effect_synced:0',
    'receipt:transaction.json','receipt:committed.json','receipts_synced','before_marker_unlink','marker_unlinked','marker_removed'])
def test_failed_protected_publication_never_replays_or_rolls_back(tmp_path,monkeypatch,kind,point):
    root,source,plan,args,target,apply=scenario(tmp_path,kind);seen=[]
    def stop(event):
        if event==point:seen.append(event);raise OSError('injected durable boundary failure')
    with monkeypatch.context() as patch:
        patch.setattr(schema_transition,'_checkpoint',stop)
        with pytest.raises(FAILURES):apply(root,plan,args)
    assert seen==[point]
    # Even a complete target/receipt cannot clear a retained owner/guard.
    assert (root/'.specroad/locks/project.json').exists()
    before=inventory(root)
    with no_write_attempts(),pytest.raises(FAILURES):apply(root,plan,args)
    assert inventory(root)==before
    from specroad.changes.normal_access import require_normal_access
    with no_write_attempts(),pytest.raises(FAILURES):require_normal_access(root)
    assert inventory(root)==before
    if point in ('marker_synced','staged:0'):
        assert all((root/p).read_bytes()==raw for p,raw in source.items())


# The real fixture contains create/replace/delete effects. Declare every index
# without invoking fixtures during collection; fail if the plan changes shape.
@pytest.mark.parametrize('index',range(13))
@pytest.mark.parametrize('boundary',['effect','sync'])
def test_every_migration_file_effect_keeps_the_actual_mixed_prefix(tmp_path,monkeypatch,index,boundary):
    root,source,plan,args,target,apply=scenario(tmp_path,'migration')
    changes=sorted(plan.data['operations'][0]['changes'],key=lambda r:r['path'])
    assert len(changes)==13
    row=changes[index]
    point=('effect_synced:' if boundary=='sync' else
           'effect_unlinked:' if row['after_bytes_base64'] is None else 'effect_replaced:')+str(index)
    seen=[]
    def stop(event):
        if event==point:seen.append(event);raise OSError('file publication interrupted')
    with monkeypatch.context() as patch:
        patch.setattr(schema_transition,'_checkpoint',stop)
        with pytest.raises(FAILURES):apply(root,plan,args)
    assert seen==[point]
    for position,effect in enumerate(changes):
        path=effect['path'];expected=(target if position<=index else source).get(path)
        if expected is None:assert not (root/path).exists()
        else:assert (root/path).read_bytes()==expected
    before=inventory(root)
    with no_write_attempts(),pytest.raises(FAILURES):apply(root,plan,args)
    assert inventory(root)==before


@pytest.mark.parametrize('kind',['migration','merge'])
@pytest.mark.parametrize('part',['transaction','request','completion','extra'])
def test_completed_proof_damage_is_rejected_without_repair(tmp_path,kind,part):
    root,source,plan,args,target,apply=scenario(tmp_path,kind);apply(root,plan,args)
    receipt=root/transaction_receipt_path(args['transaction_id'])
    path={'transaction':receipt,'completion':receipt.with_name('committed.json'),
          'request':root/request_receipt_path(plan.data['request_id']),
          'extra':receipt.with_name('foreign.json')}[part]
    path.write_bytes(path.read_bytes()+b'!' if path.exists() else b'foreign')
    before=inventory(root)
    with no_write_attempts(),pytest.raises(FAILURES):apply(root,plan,args)
    assert inventory(root)==before


def test_real_migration_process_death_cannot_supply_completion_authority(tmp_path):
    from support.command_parity import process_environment,run_python
    root,source,plan,args,target,apply=scenario(tmp_path,'migration')
    planfile=tmp_path/'plan.json';planfile.write_bytes(plan.source_bytes)
    options={k:v for k,v in args.items() if k!='authority'}
    body='''
import json,os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from specroad.changes import schema_transition
from specroad.changes.publication_values import PublicationAuthority
from specroad.migration.transaction import apply_migration_plan
schema_transition._checkpoint=lambda point: os._exit(73) if point=='effect_synced:0' else None
apply_migration_plan(sys.argv[2],Path(sys.argv[3]).read_bytes(),
    authority=PublicationAuthority('synthetic-host','1',lambda request:True),**json.loads(sys.argv[4]))
'''
    run=run_python(body,[str(Path(__file__).resolve().parents[1]/'src'),str(root),str(planfile),json.dumps(options)],
                   cwd=tmp_path,environment=process_environment())
    assert run.returncode==73,(run.stdout,run.stderr)
    from specroad.changes.write_guard_read import inspect_write_state
    state=inspect_write_state(root)
    assert state['state']=='corrupted' and state['manual_git_restore_required']
    before=inventory(root)
    with no_write_attempts(),pytest.raises(FAILURES):apply(root,plan,args)
    assert inventory(root)==before
