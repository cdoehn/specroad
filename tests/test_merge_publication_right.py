"""17.k.R: independent source races, every prefix, real recovery and tampering."""
from hashlib import sha256
from pathlib import Path
import json
import pytest
from specroad.changes.schema_transition_values import TransitionJournal,SchemaTransitionError
from specroad.changes.execution_values import ChangeExecutionError
from specroad.changes.publication_values import PublicationAuthority
from specroad.changes.recovery_values import RecoveryAuthority
from specroad.changes.core import prepare_change_plan
from specroad.changes.values import ChangePlan
from specroad.changes.locking import project_lock
from specroad.changes.receipt_values import transaction_receipt_path,request_receipt_path
from specroad.changes.recovery import (inspect_recovery,discard_unpublished_transaction,
    complete_published_transaction,rollback_interrupted_transaction)
from specroad.model.errors import ModelError
from specroad.security import SafetyViolation,ProjectBoundary
from specroad.model.canonical import canonical_json_bytes as jcs,canonical_json_sha256 as digest
from specroad.recovery.services import RestoreServices
from specroad.storage.operational_preflight import observe_operational_preflight
from specroad.migration.plan_values import b64,unb64
from support.merge_publication import setup,apply,tree,normative,seed
from support.merge_target import replace
from support.merge_resolution import ACTOR

FAILURES=(ModelError,ChangeExecutionError,SafetyViolation,OSError)


def journal(root,args):
    path=root/'.specroad/transactions'/args['transaction_id']/'journal.json'
    if not path.exists():path=(root/transaction_receipt_path(args['transaction_id'])).with_name('journal.json')
    if not path.exists():path=root/'.specroad/recovery/transaction-audit'/('schema-'+sha256(args['transaction_id'].encode()).hexdigest())/'journal.json'
    return TransitionJournal(path.read_bytes())


def recover(root,args,action):
    original=journal(root,args)
    authority=RecoveryAuthority('synthetic-merge-recovery','1',lambda request:True)
    with project_lock(root,kind='recovery',command='recover run',project_id=original.data['project_id'],
            transaction_id=args['transaction_id'],request_id=original.data['request_id']) as held:
        options=dict(held_lock=held,authority=authority,expected_journal_sha256=original.sha256)
        if action=='discard':
            return discard_unpublished_transaction(None,args['transaction_id'],actor=ACTOR,
                reason='Explicit synthetic crash recovery',**options).data
        fn=complete_published_transaction if action=='complete' else rollback_interrupted_transaction
        return fn(args['transaction_id'],**options).data


def multiple(tmp_path, *, full_registry=False):
    from support.domain import domain_value
    from support.records import record_value
    from specroad.model.paths import artifact_path
    files=seed(tmp_path/'seed',values=[record_value('document'),domain_value('goal'),domain_value('need')],
        full_registry=full_registry)
    ours=replace(files,'goal',title='Ours title')
    theirs=replace(replace(files,'goal',statement='Merged statement'),'need',title='Adopted need')
    added=domain_value('component')
    theirs[artifact_path('component',added['id'],'SR')]=jcs(added)
    return setup(tmp_path,variants=[files,ours,theirs])


def interrupt(root,plan,args,monkeypatch,point):
    from specroad.changes import schema_transition as writer
    hit=[]
    def crash(event):
        if event==point:
            hit.append(event);raise OSError('Synthetic interrupted durability boundary')
    with monkeypatch.context() as patch:
        patch.setattr(writer,'_checkpoint',crash)
        with pytest.raises(SchemaTransitionError):apply(root,plan,args)
    assert hit==[point]


@pytest.mark.parametrize('point',['journal:building:0','image:source.zip','journal:prepared:0','journal:committing:0',
    'effect:0','journal:committing:1','effect:1','journal:committing:2','effect:2','journal:committing:3',
    'journal:committed:3','receipts','archived'])
def test_every_real_prefix_has_exact_recovery_outcome_without_approval(tmp_path,monkeypatch,point):
    root,plan,args,target=multiple(tmp_path,full_registry=point in ('effect:1','archived'));before=normative(root)
    assert len(plan.data['operations'][0]['changes'])==3
    interrupt(root,plan,args,monkeypatch,point)
    current=journal(root,args)
    status=inspect_recovery(root,transaction_id=args['transaction_id']).data
    if point=='archived':action='complete'
    else:
        selected=status['transactions'][0]
        assert selected['critical_inputs_verified'] and not selected['permitted_actions']
        action='complete' if selected['complete_target_verified'] else 'discard' if current.data['state'] in ('building','prepared') else 'rollback'
    result=recover(root,args,action)
    assert result['cleanup_completed'] and result['recovery_completed']
    assert normative(root)==(target.files if action=='complete' else before)
    assert observe_operational_preflight(ProjectBoundary(root))['consistency_state']=='consistent'
    if action=='complete':
        assert not result['evidence_currently_rechecked'] and not result['approval_granted']
        assert apply(root,plan,args)['replayed']
    else:
        assert not (root/request_receipt_path(plan.data['request_id'])).exists()


@pytest.mark.parametrize('role',['base','ours','theirs'])
def test_real_source_change_from_authority_is_detected_before_journal(tmp_path,role):
    root,plan,args,target=setup(tmp_path)
    source=getattr(args['sources'],role)
    path=Path(source.source_root)/next(p for p in source.files if p.startswith('spec/goals/'))
    before=normative(root)
    def change(request):
        path.write_bytes(path.read_bytes()+b'\n');return True
    args['authority']=PublicationAuthority('synthetic-race','1',change)
    with pytest.raises(FAILURES):apply(root,plan,args)
    assert not (root/'.specroad/transactions'/args['transaction_id']).exists()
    if role!='ours':assert normative(root)==before
    else:assert path.read_bytes()==before[path.relative_to(root).as_posix()]+b'\n'


@pytest.mark.parametrize('part',['target','metadata','history','effect'])
def test_rehashed_forgery_cannot_replace_native_reconstruction(tmp_path,part):
    root,plan,args,target=setup(tmp_path);data=plan.data;data.pop('change_plan_sha256')
    op=data['operations'][0];inputs=op['inputs']
    if part in ('target','metadata'):
        key=part+'_bytes_base64';value=json.loads(unb64(inputs[key]))
        value['approval_granted']=True;raw=jcs(value)
        inputs[key]=b64(raw);inputs[part+'_sha256']=sha256(raw).hexdigest();op['inputs_sha256']=digest(inputs)
    elif part=='history':
        inputs['history']['observations'][0]['origin']['creation_event']='Forged origin'
        op['inputs_sha256']=digest(inputs)
    else:
        row=op['changes'][0];value=json.loads(unb64(row['after_bytes_base64']));value['title']='Forged'
        raw=jcs(value);row['after_bytes_base64']=b64(raw);row['after_sha256']=sha256(raw).hexdigest()
        for file in op['target_files']:
            if file['path']==row['path']:file.update(size=len(raw),sha256=row['after_sha256'])
        for item in data['result_artifacts']:
            if item['artifact']['id']==value['id']:item.update(artifact=value,sha256=digest(value))
    forged=prepare_change_plan(data);before=tree(root)
    args['expected_plan_sha256']=forged.sha256
    with pytest.raises(FAILURES):apply(root,forged,args)
    assert tree(root)==before


@pytest.mark.parametrize('part',['backup','journal','before','staging'])
def test_tampered_recovery_original_is_never_discarded_or_silently_repaired(tmp_path,monkeypatch,part):
    root,plan,args,target=multiple(tmp_path)
    interrupt(root,plan,args,monkeypatch,'journal:prepared:0')
    prefix=root/'.specroad/transactions'/args['transaction_id']
    path=Path(args['backup_descriptor']['path']) if part=='backup' else prefix/('journal.json' if part=='journal' else part+'/0.bin')
    if part=='before':path=next((prefix/'before').glob('*.bin'))
    path.write_bytes(path.read_bytes()+b'changed')
    before=tree(root)
    with pytest.raises(FAILURES):recover(root,args,'discard')
    assert tree(root)==before


def test_published_receipt_remains_historical_if_external_bytes_change_at_archive(tmp_path,monkeypatch):
    from support.records import record_value
    from specroad.changes import schema_transition as writer
    code=tmp_path/'code';code.mkdir();raw=b'original\n';path=code/'source.py';path.write_bytes(raw)
    files=seed(tmp_path/'seed',values=[record_value('document'),record_value('code_ref',reference_kind='file',
        path='source.py',file_sha256=sha256(raw).hexdigest())])
    service=RestoreServices(code_source=lambda model,record:ProjectBoundary(code))
    root,plan,args,target=setup(tmp_path,variants=[files]*3,services=service)
    def change(event):
        if event=='archived':path.write_bytes(b'changed code\n')
    with monkeypatch.context() as patch:
        patch.setattr(writer,'_checkpoint',change)
        with pytest.raises(SchemaTransitionError):apply(root,plan,args)
    assert journal(root,args).data['state']=='committed'
    assert normative(root)==target.files
    replay=apply(root,plan,args)
    assert replay['replayed'] and not replay['evidence_currently_rechecked']
    assert not replay['current_target_verified'] and not replay['approval_granted']


def test_same_request_with_different_operations_conflicts_after_verified_receipt(tmp_path):
    root,plan,args,target=setup(tmp_path);apply(root,plan,args)
    value=plan.data;value.pop('change_plan_sha256')
    value['operations'][0]['inputs']['history']['observations'][0]['origin']['creation_event']='Another operation input'
    value['operations'][0]['inputs_sha256']=digest(value['operations'][0]['inputs'])
    changed=prepare_change_plan(value);args['expected_plan_sha256']=changed.sha256;before=tree(root)
    with pytest.raises(FAILURES):apply(root,changed,args)
    assert tree(root)==before
