"""Target integrity and full-supplied-model gates, never console formatting."""
from copy import deepcopy
from hashlib import sha256
import json
import pytest
from specroad.changes import (assess_change_target, TargetError, TargetPolicy, TargetModel, ChangePlan)
from specroad.model.canonical import canonical_json_sha256, canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.validation import ModelDocument
from support.folds import goal, edit, add_relation, create
from support.targets import model, plan, gate, resign, POLICY, SCOPE


def test_target_hash_diff_and_single_revision_are_recomputed():
    a=goal(); m=model([a]); p=plan(m,[edit(a,'Changed')]); r=assess_change_target(p,m,policy=POLICY)
    assert r.target_validated and r.require_valid() is r
    assert r.data['target_manifest']['scope_sha256'] == m.manifest(r.artifacts,SCOPE).scope_sha256
    assert r.data['binding']['target_model_root'] == p.data['expected_result']['model_root_sha256']
    assert r.artifacts[0]['revision']==a['revision']+1
    assert r.data['diff']['changes'][0]['artifact_id']==a['id']
    assert any(d['pointer']=='/statement' for d in r.data['diff']['changes'][0]['fields'])


def test_entire_unchanged_target_is_given_to_every_registered_gate():
    a,b=goal(),goal(1);m=model([a,b]);p=plan(m,[edit(a,'Changed')]); observed=[]
    def check(c):
        observed.append((c.subjects,c.artifact(b['id'])))
        return c.result()
    r=assess_change_target(p,m,policy=POLICY,gates=[gate(check=check)])
    assert r.target_validated and observed==[((a['id'],b['id']),b)]
    assert r.data['validation']['source_report']['requested_ids'] is None


def test_error_in_unmodified_dependent_artifact_blocks_target():
    a,b=goal(),goal(1);b['relations']=[add_relation(b,a)['relation']]
    m=model([a,b]);p=plan(m,[edit(a,'Incompatible')])
    def check(c):
        return c.result([{'reason':'dependent_contract_failed','severity':'error','artifact_id':b['id']}])
    r=assess_change_target(p,m,policy=POLICY,gates=[gate(check=check)])
    assert not r.target_validated
    assert b in r.artifacts and b['id'] in r.data['validation']['source_report']['checked_ids']
    with pytest.raises(TargetError):r.require_valid()


def test_missing_command_gate_is_not_success():
    a=goal();m=model([a]);p=plan(m,[])
    policy=TargetPolicy('command','1',('extension:required',))
    r=assess_change_target(p,m,policy=policy)
    assert not r.target_validated and r.data['missing_command_gates']==['extension:required']
    assert assess_change_target(p,m,policy=policy,gates=[gate('extension:required')]).target_validated


def test_missing_core_lifecycle_gate_is_not_optional():
    a=goal(maturity='proposed');m=model([a]);p=plan(m,[])
    r=assess_change_target(p,m,policy=POLICY)
    assert not r.target_validated
    assert any(s['stage']=='lifecycle' and s['status']=='unavailable' for s in r.data['validation']['source_report']['stages'])


@pytest.mark.parametrize('side',['base','expected_result'])
def test_self_consistent_plan_with_wrong_model_root_is_rejected(side):
    a=goal();m=model([a]);p=plan(m,[edit(a,'X')])
    forged=resign(p,lambda d:d[side].update(model_root_sha256='a'*64))
    with pytest.raises(TargetError):assess_change_target(forged,m,policy=POLICY)


def test_false_result_metadata_with_recomputed_hash_does_not_pass():
    a=goal();m=model([a]);p=plan(m,[edit(a,'X')])
    def change(d):
        entry=d['result_artifacts'][0];entry['artifact']['revision']+=1
        entry['sha256']=canonical_json_sha256(entry['artifact'])
    with pytest.raises(ModelError):assess_change_target(resign(p,change),m,policy=POLICY)


def test_damaged_plan_self_hash_is_rejected_again():
    a=goal();m=model([a]);p=plan(m,[edit(a,'X')]);data=p.data;data['request_id']='changed'
    object.__setattr__(p,'source_bytes',canonical_json_bytes(data))
    with pytest.raises(ModelError):assess_change_target(p,m,policy=POLICY)


def test_original_input_and_returned_values_are_independent():
    a=goal();ops=[edit(a,'X')];before=deepcopy((a,ops));m=model([a]);p=plan(m,ops)
    r=assess_change_target(p,m,policy=POLICY);out=r.data;out['target_validated']=False
    r.artifacts[0]['statement']='tampered'
    assert (a,ops)==before and r.target_validated and r.artifacts[0]['statement']=='X'
    assert m.artifacts==[a] and r.plan.source_bytes==p.source_bytes


def test_noop_preserves_original_bytes_and_semantic_root():
    a=goal();m=model([a]);d=m.documents[0]
    raw=json.dumps(a,indent=4,ensure_ascii=False).encode()
    m=TargetModel(m.configuration_bytes,m.binding,[ModelDocument(d.path,raw)],
                  profile=m.profile,resource_files=m.resource_files)
    p=plan(m,[]);r=assess_change_target(p,m,policy=POLICY)
    assert r.target_validated and r.documents[0].content==raw
    assert r.data['binding']['base_model_root']==r.data['binding']['target_model_root']
    assert not r.data['diff']['changed'] and r.data['impact']['after']['items']==[]


def test_impact_keeps_both_removed_and_added_connections():
    from support.folds import remove_relation
    a,b,c=goal(),goal(1),goal(2);a['relations']=[add_relation(a,b)['relation']]
    m=model([a,b,c]);p=plan(m,[remove_relation(a,a['relations'][0]),add_relation(a,c,2)])
    r=assess_change_target(p,m,policy=POLICY)
    impact=r.data['impact'];assert impact['depth']==1 and not impact['transitive']
    assert impact['before']['items'][0]['groups'][0]['artifact_ids']==[b['id']]
    assert impact['after']['items'][0]['groups'][0]['artifact_ids']==[c['id']]


def test_true_warning_threshold_preserves_warning_severity():
    a=goal();m=model([a]);p=plan(m,[])
    g=gate(check=lambda c:c.result([{'reason':'review_warning','severity':'warning'}]))
    assert assess_change_target(p,m,policy=POLICY,gates=[g]).target_validated
    r=assess_change_target(p,m,policy=POLICY,gates=[g],strict=True)
    assert not r.target_validated
    assert r.data['validation']['diagnostics'][0]['severity']=='warning'


def test_old_gate_result_is_not_reused_for_another_plan():
    a=goal();m=model([a]);p=plan(m,[]);cached=[]
    def check(c):
        if not cached:cached.append(c.result())
        return cached[0]
    g=gate(check=check)
    assert assess_change_target(p,m,policy=POLICY,gates=[g]).target_validated
    q=plan(m,[],request_id='second')
    assert not assess_change_target(q,m,policy=POLICY,gates=[g]).target_validated


def test_target_hierarchy_error_is_found_by_the_shared_pipeline():
    a,b=goal(),goal(1);m=model([a,b])
    p=plan(m,[add_relation(a,b,1,kind='supersedes'),add_relation(b,a,2,kind='supersedes')])
    r=assess_change_target(p,m,policy=POLICY)
    assert not r.target_validated
    assert any(s['stage']=='graph' and s['status']=='failed' for s in r.data['validation']['source_report']['stages'])


def test_registered_checker_failure_never_produces_valid_target():
    a=goal();m=model([a]);p=plan(m,[])
    def check(c):raise RuntimeError('failure')
    r=assess_change_target(p,m,policy=POLICY,gates=[gate(check=check)])
    assert not r.target_validated and r.data['validation']['exit_code']==4


def test_external_paths_do_not_change_canonical_model_root():
    from specroad.model.model_manifest import ProjectReadBinding
    a=goal();m=model([a]);other=model([a],binding=ProjectReadBinding('sample','/different/path',(99,88)))
    p=plan(m,[edit(a,'X')])
    assert assess_change_target(p,m,policy=POLICY).data['target_manifest']==assess_change_target(p,other,policy=POLICY).data['target_manifest']


def test_non_project_partial_and_configured_scopes_are_not_claimed_complete():
    a=goal();m=model([a]);p=plan(m,[edit(a,'X')])
    q=resign(p,lambda d:d['base']['scope_descriptor'].update(boundary_policy='partial'))
    with pytest.raises(ModelError):assess_change_target(q,m,policy=POLICY)


def test_resource_content_change_invalidates_old_base_root():
    from support.profiles import profile_data
    a=goal();m=model([a]);p=plan(m,[])
    changed=model([a],profiles=[profile_data(profile_id='core',description='different')])
    with pytest.raises(ModelError):assess_change_target(p,changed,policy=POLICY)


def test_required_profile_resource_cannot_be_omitted():
    a=goal();m=model([a])
    with pytest.raises(ModelError):TargetModel(m.configuration_bytes,m.binding,m.documents,profile=m.profile)


def test_preconditions_use_actual_source_bytes():
    a=goal();m=model([a]);d=m.documents[0]
    p=plan(m,[],preconditions=[{'kind':'file','path':d.path,'expected_byte_sha256':sha256(d.content).hexdigest()}])
    assert assess_change_target(p,m,policy=POLICY).target_validated
    changed=TargetModel(m.configuration_bytes,m.binding,[ModelDocument(d.path,json.dumps(a,indent=3).encode())],
                        profile=m.profile,resource_files=m.resource_files)
    with pytest.raises(ModelError):assess_change_target(p,changed,policy=POLICY)


def test_empty_model_with_explicit_profile_is_validated_without_false_writes():
    m=model([]);r=assess_change_target(plan(m,[]),m,policy=POLICY)
    assert r.target_validated and not r.transaction_prepared and not r.execution_ready and not r.write_authorized
    assert r.data['atomic_snapshot'] is False and r.artifacts==[]
    with pytest.raises(TypeError):bool(r)
