"""17.k.W: real shared writer, exact K.3 bytes and newly assessed evidence."""
from hashlib import sha256
from pathlib import Path
import json
import pytest
from specroad.merge import plan_merge_publication,apply_merge_publication
from specroad.changes.schema_transition_values import TransitionJournal,SchemaTransitionError
from specroad.changes.receipt_values import transaction_receipt_path,request_receipt_path
from specroad.changes.publication_values import PublicationAuthority
from specroad.changes.values import ChangePlan
from specroad.changes.core import prepare_change_plan
from specroad.changes.authoring import prepare_authoring_request
from specroad.model.errors import ModelError
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.recovery.services import RestoreServices
from support.merge_target import seed,replace
from support.merge_publication import setup,apply,tree,normative


@pytest.mark.parametrize('variant',['unchanged','adopted','combined'])
def test_exact_k3_bytes_use_shared_transaction_and_bound_native_report(tmp_path,variant):
    files=seed(tmp_path/'seed')
    ours=replace(files,'goal',title='Ours') if variant=='combined' else files
    theirs=replace(files,'goal',statement='Theirs') if variant!='unchanged' else files
    root,plan,args,target=setup(tmp_path,variants=[files,ours,theirs])
    before=normative(root)
    result=apply(root,plan,args)
    assert result['format_version']=='merge-transaction-v1' and result['write_state']=='committed'
    assert result['current_target_verified'] and result['evidence_currently_rechecked'] and not result['approval_granted']
    assert normative(root)==target.files
    goal_path=next(p for p in ours if p.startswith('spec/goals/'))
    actual_goal=json.loads((root/goal_path).read_bytes())
    assert actual_goal['title']==json.loads(ours[goal_path])['title']
    assert actual_goal['statement']==('Theirs' if variant!='unchanged' else json.loads(ours[goal_path])['statement'])
    if variant=='adopted':assert (root/goal_path).read_bytes()==theirs[goal_path]
    if variant=='unchanged':assert (root/goal_path).read_bytes()==ours[goal_path]
    assert result['target_model_root_sha256']==target.data['expected_target_model_root_sha256']
    report=result['validation']
    assert report['native']['checks_complete'] and report['native']['model_valid']
    assert report['assessment']==target.data['validation']
    assert report['relation_reviews']==report['evidence']==report['code_references']==[]
    tx=root/transaction_receipt_path(args['transaction_id'])
    journal=TransitionJournal(tx.with_name('journal.json').read_bytes())
    assert journal.data['format_version']=='merge-transition-journal-v1'
    assert journal.plan.source_bytes==plan.source_bytes and journal.data['validation']==report
    assert sha256(tx.read_bytes()).hexdigest()==result['receipts']['transaction']['sha256']
    assert (root/request_receipt_path(plan.data['request_id'])).is_file()
    assert not (root/'.specroad/transactions'/args['transaction_id']).exists()
    assert not (root/'.specroad/locks/project.json').exists()
    assert before==ours


def test_publication_refuses_missing_or_negative_real_host_authority(tmp_path):
    root,plan,args,target=setup(tmp_path);before=tree(root)
    args['authority']=PublicationAuthority('synthetic-denied','1',lambda request:False)
    with pytest.raises(SchemaTransitionError,match='transition_not_authorized'):apply(root,plan,args)
    assert tree(root)==before
    args['authority']=True
    with pytest.raises(ModelError):apply(root,plan,args)
    assert tree(root)==before


def test_regular_authoring_cannot_relabel_or_inject_merge_operation(tmp_path):
    root,plan,args,target=setup(tmp_path)
    with pytest.raises(ModelError):
        prepare_authoring_request(command_id='change apply',actor=plan.data['actor'],operations=plan.data['operations'])
    value=plan.data;value.pop('change_plan_sha256');value['metadata_policy_version']='change-metadata-v1'
    with pytest.raises(ModelError):prepare_change_plan(value)
    value=plan.data;value.pop('change_plan_sha256');value['operations']*=2
    with pytest.raises(ModelError):prepare_change_plan(value)


@pytest.mark.parametrize('change',['existing','extra'])
def test_stale_current_ours_or_extra_normative_file_is_not_silently_rebased(tmp_path,change):
    root,plan,args,target=setup(tmp_path)
    if change=='existing':
        path=next(root.glob('spec/goals/*.json'));path.write_bytes(path.read_bytes()+b'\n')
    else:
        from support.domain import domain_value
        from specroad.model.paths import artifact_path
        value=domain_value('need');path=root/artifact_path('need',value['id'],'SR')
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(jcs(value))
    before=tree(root)
    with pytest.raises((ModelError,SchemaTransitionError)):apply(root,plan,args)
    assert tree(root)==before


def test_request_replay_is_historical_and_never_reexecutes_or_requalifies(tmp_path):
    root,plan,args,target=setup(tmp_path);first=apply(root,plan,args)
    path=next(root.glob('spec/goals/*.json'));value=json.loads(path.read_bytes())
    value['title']='Later independent change';value['revision']+=1;path.write_bytes(jcs(value))
    Path(args['backup_descriptor']['path']).unlink()
    before=tree(root);inodes={p:(root/p).stat().st_ino for p in before}
    again=apply(root,plan,args)
    assert again['replayed'] and not again['current_target_verified'] and not again['evidence_currently_rechecked']
    assert again['validation']==first['validation']
    assert tree(root)==before and inodes=={p:(root/p).stat().st_ino for p in before}


def test_real_external_code_bytes_are_rechecked_for_completion(tmp_path):
    from support.records import record_value
    from specroad.security import ProjectBoundary
    code=tmp_path/'code';code.mkdir();raw=b'original code\n';(code/'module.py').write_bytes(raw)
    record=record_value('code_ref',path='module.py',file_sha256=sha256(raw).hexdigest(),reference_kind='file')
    files=seed(tmp_path/'seed',values=[record_value('document'),record])
    services=RestoreServices(code_source=lambda model,record:ProjectBoundary(code))
    root,plan,args,target=setup(tmp_path,variants=[files]*3,services=services)
    result=apply(root,plan,args)
    assert result['validation']['code_references'][0]['state']=='current'
    assert result['validation']['code_references'][0]['reference_state_evaluated']
    assert normative(root)==target.files


def test_changed_relation_context_preserves_review_original_as_suspect(tmp_path):
    from support.records import record_value
    from test_relation_review_status import endpoints,review
    first,second=endpoints()
    original_review=review(first,second)
    files=seed(tmp_path/'seed',values=[record_value('document'),first,second,original_review])
    theirs=replace(files,'goal',identifier=second['id'],title='Changed context')
    root,plan,args,target=setup(tmp_path,variants=[files,files,theirs])
    result=apply(root,plan,args)
    statuses=result['validation']['relation_reviews']
    assert statuses[0]['status']=='suspect'
    path=next(p for p,b in files.items() if p.startswith('spec/') and json.loads(b)['id']==original_review['id'])
    assert (root/path).read_bytes()==files[path]


def test_changed_evidence_subject_is_reassessed_without_rewriting_the_record(tmp_path):
    from support.records import record_value
    from test_verification_run_selection import case,observation
    records,evaluation,_,key=case(policy='independent',configured=False)
    evidence=observation(records,evaluation,key,result='passed')
    evidence['configuration_policy']='independent'
    files=seed(tmp_path/'seed',values=[record_value('document'),*records,evidence])
    theirs=replace(files,'requirement',statement='Changed verification subject')
    root,plan,args,target=setup(tmp_path,variants=[files,files,theirs])
    result=apply(root,plan,args)
    assert any(row['freshness']=='stale' for row in result['validation']['evidence'])
    path=next(p for p,b in files.items() if p.startswith('spec/') and json.loads(b)['id']==evidence['id'])
    assert (root/path).read_bytes()==files[path]
