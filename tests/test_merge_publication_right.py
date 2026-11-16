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
from specroad.qualification.services import RestoreServices
from specroad.storage.operational_preflight import observe_operational_preflight
from specroad.migration.plan_values import b64,unb64
from support.merge_publication import setup,apply,tree,normative,seed
from support.merge_target import replace
from support.merge_resolution import ACTOR

FAILURES=(ModelError,ChangeExecutionError,SafetyViolation,OSError)








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






def test_same_request_with_different_operations_conflicts_after_verified_receipt(tmp_path):
    root,plan,args,target=setup(tmp_path);apply(root,plan,args)
    value=plan.data;value.pop('change_plan_sha256')
    value['operations'][0]['inputs']['history']['observations'][0]['origin']['creation_event']='Another operation input'
    value['operations'][0]['inputs_sha256']=digest(value['operations'][0]['inputs'])
    changed=prepare_change_plan(value);args['expected_plan_sha256']=changed.sha256;before=tree(root)
    with pytest.raises(FAILURES):apply(root,changed,args)
    assert tree(root)==before
