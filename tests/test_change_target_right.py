"""Full target and plan tampering regressions; no visual or documentation oracles."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
import pytest
from specroad.changes import (TargetModel, TargetPolicy, TargetError, TargetAssessment,
                              prepare_change_target, assess_change_target, ChangePlan)
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.paths import artifact_path
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument, ModelGate, GateResult
from support.folds import goal, edit, create, add_relation
from support.domain import domain_value, approved_value
from support.profiles import profile_data, selector
from support.targets import model, plan, gate, resign, POLICY, SCOPE, ACTOR, TIME


def prepare(m, ops, **kw):
    options = {'change_plan_id':'CP-explicit', 'request_id':'request-1', 'actor':ACTOR,
               'planned_at':TIME, 'scope_descriptor':SCOPE,
               'metadata_policy_version':'change-metadata-v1', 'policy':POLICY}
    options.update(kw)
    return prepare_change_target(m, ops, **options)


def copied(m, **kw):
    opts = {'profile':m.profile, 'resource_files':m.resource_files,
            'attachments':m.attachment_descriptors, 'language_packages':m.language_packages,
            **m.reservations}
    opts.update(kw)
    return TargetModel(m.configuration_bytes, m.binding, m.documents, **opts)


def test_authoring_and_saved_plan_paths_produce_identical_observations():
    a=goal();m=model([a]);ops=[edit(a,'New')]
    r=prepare(m,ops);s=assess_change_target(r.plan,m,policy=POLICY)
    assert r.data==s.data and r.documents==s.documents
    assert r.plan.canonical_bytes==plan(m,ops).canonical_bytes


@pytest.mark.parametrize('key,value',[
    ('metadata_policy_version','unknown'), ('actor',{'actor_type':'human'}),
    ('planned_at','tomorrow'), ('change_plan_id',''), ('request_id',' invalid')])
def test_authoring_metadata_is_explicit_and_not_guessed(key,value):
    with pytest.raises(ModelError): prepare(model([goal()]),[],**{key:value})


def test_unmodified_foreign_field_reference_error_blocks_whole_target():
    a=goal();inter=domain_value('interface')
    m=model([a,inter]);r=prepare(m,[edit(a,'New')])
    assert not r.target_validated
    report=r.data['validation']['source_report']
    assert any(d['reason']=='validation_field_target_missing' for stage in report['stages'] for d in stage['diagnostics'])
    assert inter['id'] in report['identified_ids']


def test_profile_constraints_on_unmodified_artifact_are_not_skipped():
    a,b=goal(),goal(1);b['owner']='forbidden'
    resource=profile_data(profile_id='core',allowed_values=[
        selector(artifact_types=['goal'],field='/owner',values=['product'])])
    m=model([a,b],profiles=[resource]);r=prepare(m,[edit(a,'New')])
    assert not r.target_validated
    assert any(d.get('artifact_id')==b['id'] for stage in r.data['validation']['source_report']['stages'] for d in stage['diagnostics'])


def test_partial_gate_result_is_not_a_success():
    a,b=goal(),goal(1);m=model([a,b])
    def check(c):return GateResult(c.input_sha256,[c.subjects[0]])
    r=prepare(m,[],gates=[gate(check=check)])
    assert not r.target_validated


def test_dependency_phase_must_cover_all_subjects():
    m=model([goal(),goal(1)])
    g=ModelGate('extension:missing','1',lambda c:c.dependency_result({c.subjects[0]:[]}),lambda c:c.result())
    assert not prepare(m,[],gates=[g]).target_validated


def test_dependency_must_exist_even_outside_changed_ids():
    a=goal();missing=goal(99)
    g=ModelGate('extension:missing','1',lambda c:c.dependency_result({a['id']:[missing['id']]}),lambda c:c.result())
    assert not prepare(model([a]),[],gates=[g]).target_validated


def test_gate_versions_and_command_policy_are_part_of_binding():
    m=model([goal()]);saved=[]
    def checker(c):
        if not saved:saved.append(c.result())
        return saved[0]
    first=prepare(m,[],gates=[gate(check=checker)])
    assert first.target_validated
    assert not prepare(m,[],gates=[gate(check=checker,version='2')]).target_validated
    assert not prepare(m,[],gates=[gate(check=checker)],policy=TargetPolicy('other','1',())).target_validated


def test_successful_gate_for_old_target_cannot_reuse_outcome():
    a=goal();m=model([a]);stored=[]
    def checker(c):
        if not stored:stored.append(c.result())
        return stored[0]
    assert prepare(m,[],gates=[gate(check=checker)]).target_validated
    assert not prepare(m,[edit(a,'Changed')],gates=[gate(check=checker)]).target_validated


def test_duplicate_registered_gate_cannot_masquerade_as_two_checks():
    with pytest.raises(TargetError):prepare(model([goal()]),[],gates=[gate(),gate()])


def test_policy_cannot_disable_core_checks_or_guess_required_gates():
    for value in [('lifecycle',),('extension:',),('extension:a','extension:a'),['extension:a']]:
        with pytest.raises(TargetError):TargetPolicy('command','1',value)
    a=goal(maturity='proposed');m=model([a])
    assert not prepare(m,[],policy=TargetPolicy('command','1',())).target_validated
    assert prepare(m,[],gates=[gate('lifecycle')]).target_validated


@pytest.mark.parametrize('field,value',[
    ('actor',{'actor_type':'ci','actor_id':'other'}),('planned_at','2027-01-01T00:00:00Z'),
    ('metadata_policy_version','migrate-copy-v1')])
def test_changed_plan_binding_cannot_keep_old_results(field,value):
    a=goal();m=model([a]);p=plan(m,[edit(a,'Changed')])
    with pytest.raises(ModelError):
        q=resign(p,lambda d:d.update({field:value}))
        assess_change_target(q,m,policy=POLICY)


def test_advertised_expected_root_cannot_be_swapped_for_another_valid_plan():
    a=goal();m=model([a]);p=plan(m,[edit(a,'One')]);q=plan(m,[edit(a,'Two')])
    forged=resign(p,lambda d:d.update(expected_result=q.data['expected_result']))
    with pytest.raises(TargetError):assess_change_target(forged,m,policy=POLICY)


def test_registry_of_target_gates_is_not_read_from_extensions():
    a=goal(extensions={'sample.gates':{'approved':True,'command':'bypass'}});m=model([a])
    r=prepare(m,[],policy=TargetPolicy('command','1',('extension:required',)))
    assert not r.target_validated and r.data['missing_command_gates']==['extension:required']


def test_historical_and_reserved_ids_remain_reserved():
    a,b=goal(),goal(1);m=model([a])
    for key in ('previously_approved_ids','reserved_artifact_ids'):
        reserved=copied(m,**{key:[b['id']]})
        with pytest.raises(ModelError):prepare(reserved,[create(b)])
        r=prepare(reserved,[edit(a,'New')])
        assert r.target_validated and not r.data['lifecycle']['history_complete']


def test_reserved_relations_remain_unavailable_to_new_operations():
    a,b=goal(),goal(1);m=model([a,b]);op=add_relation(a,b)
    reserved=copied(m,reserved_relation_ids=[op['relation']['relation_id']])
    with pytest.raises(ModelError):prepare(reserved,[op])


def test_history_change_binds_gate_even_if_final_artifacts_do_not_change():
    m=model([goal()]);stored=[]
    def checker(c):
        if not stored:stored.append(c.result())
        return stored[0]
    assert prepare(m,[],gates=[gate(check=checker)]).target_validated
    other=copied(m,previously_approved_ids=[goal(99)['id']])
    assert not prepare(other,[],gates=[gate(check=checker)]).target_validated


def test_reservation_mutations_and_wrong_project_are_rejected():
    m=model([goal()]);ids=[goal(99)['id']];other=copied(m,previously_approved_ids=ids);ids.clear()
    assert other.previously_approved_ids
    for values in ([goal(99)['id']]*2,['OTHER-GOAL-'+'0'*26],['not-an-id']):
        with pytest.raises(ModelError):copied(m,previously_approved_ids=values)


def test_source_document_objects_are_owned_snapshots():
    a=goal();m=model([a]);original=m.documents[0]
    other=TargetModel(m.configuration_bytes,m.binding,[original],profile=m.profile,resource_files=m.resource_files)
    object.__setattr__(original,'content',canonical_json_bytes({**a,'statement':'forged'}))
    assert other.artifacts==[a]
    with pytest.raises(TargetError):prepare(m,[])


def test_cached_resource_metadata_is_not_trusted_over_raw_files():
    m=model([goal()]);p=plan(m,[]);baseline=assess_change_target(p,m,policy=POLICY).data
    object.__setattr__(m,'resources',())
    assert assess_change_target(p,m,policy=POLICY).data==baseline


def test_effective_profile_cannot_be_forged_in_place():
    m=model([goal()]);data=m.profile.data;data['merge']['required_fields']=[]
    data['profiles'][0]['sha256']='a'*64
    object.__setattr__(m.profile,'_encoded',canonical_json_bytes(data))
    with pytest.raises(ModelError):prepare(m,[])


def test_different_raw_profile_layout_keeps_root_but_invalidates_old_gate_evidence():
    m=model([goal()]);d=m.resource_files[0];changed=ModelDocument(d.path,json.dumps(json.loads(d.content),indent=7).encode())
    other=copied(m,resource_files=[changed]);assert m.manifest(m.artifacts,SCOPE).sha256==other.manifest(other.artifacts,SCOPE).sha256
    results=[]
    def checker(c):
        if not results:results.append(c.result())
        return results[0]
    assert prepare(m,[],gates=[gate(check=checker)]).target_validated
    assert not prepare(other,[],gates=[gate(check=checker)]).target_validated


def test_config_semantics_and_actual_bytes_are_both_bound():
    a=goal();m=model([a]);p=plan(m,[])
    d=m.configuration.data;d['project_id']='other'
    with pytest.raises(ModelError):TargetModel(canonical_json_bytes(d),m.binding,m.documents,profile=m.profile,resource_files=m.resource_files)
    d=m.configuration.data;d['validation_policy']['fail_on']='warning'
    other=TargetModel(canonical_json_bytes(d),m.binding,m.documents,profile=m.profile,resource_files=m.resource_files)
    with pytest.raises(ModelError):assess_change_target(p,other,policy=POLICY)


def test_duplicate_resource_identity_under_another_path_is_not_allowed():
    m=model([goal()]);d=m.resource_files[0]
    with pytest.raises(ModelError):copied(m,resource_files=[d,ModelDocument('profiles/other.json',d.content)])


def test_new_reference_and_its_required_artifact_must_exist_in_target():
    a,b=goal(),goal(1,created_at=TIME,updated_at=TIME,created_by=ACTOR,updated_by=ACTOR);m=model([a])
    r=prepare(m,[create(b),add_relation(a,b)])
    assert r.target_validated and len(r.artifacts)==2
    with pytest.raises(ModelError):prepare(m,[add_relation(a,b),create(b)])


def test_missing_and_same_length_changed_attachment_bytes_are_rejected():
    from support.records import record_value
    blob=b'abc';desc=AttachmentDescriptor('attachments/a.bin','application/octet-stream',len(blob),sha256(blob).hexdigest())
    subject=goal()
    a=record_value('evidence',subjects=[{'artifact_id':subject['id'],'revision':1,
        'artifact_sha256':canonical_json_sha256(subject),'verification_context_sha256':'a'*64}],
        attachments=[desc.data]);f=ModelDocument(desc.path,blob)
    for files in ([],[ModelDocument(desc.path,b'xyz')]):
        with pytest.raises(ModelError):model([a,subject],attachments=[desc],resource_files=files)
    m=model([a,subject],attachments=[desc],resource_files=[f])
    r=prepare(m,[])
    assert not r.target_validated # Byte integrity alone is not genuine evidence/currentness.
    assert r.data['target_manifest']['attachments'][0]['sha256']==desc.sha256


def test_extra_resource_bytes_are_bound_even_if_no_artifact_was_changed():
    a=goal();f=ModelDocument('rules/one.json',canonical_json_bytes({'schema_version':'0.2.0','rule_id':'one','version':'1.0.0','payload':1}))
    m=model([a],resource_files=[f]);p=plan(m,[])
    changed=ModelDocument(f.path,canonical_json_bytes({'schema_version':'0.2.0','rule_id':'one','version':'1.0.0','payload':2}))
    other=model([a],resource_files=[changed])
    with pytest.raises(ModelError):assess_change_target(p,other,policy=POLICY)


def test_unknown_resource_types_do_not_become_unchecked_model_members():
    for path in ('generated/x.json','.specroad/cache/x','outside.json'):
        with pytest.raises(ModelError):model([goal()],resource_files=[ModelDocument(path,b'{}')])


def test_references_inside_free_text_and_extensions_do_not_read_more_files():
    a=goal(statement='See ../../outside.json',extensions={'example.path':'/etc/passwd'})
    r=prepare(model([a]),[])
    assert r.target_validated and r.artifacts==[a]


def test_target_assessment_has_no_environment_time_or_filesystem_access(monkeypatch):
    import builtins,io,os,time,uuid,subprocess
    a=goal();m=model([a])
    def blocked(*args,**kwargs):raise AssertionError('unexpected I/O or ambient identity')
    for module,name in [(builtins,'open'),(io,'open'),(os,'open'),(os,'getlogin'),
                        (time,'time'),(uuid,'uuid4'),(subprocess,'Popen')]:
        monkeypatch.setattr(module,name,blocked)
    assert prepare(m,[edit(a,'New')]).target_validated


def test_foreign_mapping_callbacks_are_not_used_for_operations():
    class Foreign(dict):
        def items(self):raise AssertionError('callback ran')
    with pytest.raises(ModelError):prepare(model([goal()]),[Foreign(edit(goal(),'X'))])


def test_independent_noops_preserve_all_originals_and_empty_impact():
    a=goal();m=model([a]);r=prepare(m,[edit(a,'Temporary'),edit(a,a['statement'])])
    assert r.artifacts==[a] and r.documents==m.documents
    assert not r.data['diff']['changed'] and not r.data['impact']['after']['items']
    assert r.data['binding']['base_model_root']==r.data['binding']['target_model_root']


def test_parallel_calls_share_no_mutable_decisions_or_gate_inputs():
    a=goal();m=model([a]);ops=[edit(a,'New')]
    with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(lambda _:prepare(m,ops).data,range(12)))
    assert all(row==rows[0] for row in rows)
    rows[0]['validation'].clear();assert rows[1]['validation'] and m.artifacts==[a]


def test_whole_target_not_limited_to_150_artifacts_or_changed_subjects():
    values=[goal(n) for n in range(153)];m=model(values);seen=[]
    def checker(c):seen.extend(c.subjects);return c.result()
    r=prepare(m,[edit(values[0],'New')],gates=[gate(check=checker)])
    assert r.target_validated and len(seen)==153 and len(set(seen))==153
    assert len(r.artifacts)==153 and len(r.data['diff']['changes'])==1


def test_original_source_reordering_does_not_change_canonical_assessment():
    a,b=goal(),goal(1);first=model([a,b]);second=model([b,a])
    assert prepare(first,[edit(a,'New')]).data==prepare(second,[edit(a,'New')]).data


def test_shifted_portable_distributions_run_target_validation(tmp_path):
    from support.portable import build_distribution
    from support.processes import run_python
    module,archive=build_distribution(tmp_path/'delivery')
    moved=tmp_path/'moved';module.rename(moved);movedzip=tmp_path/'moved.pyz';archive.rename(movedzip)
    m=model([goal()]);ops=[edit(goal(),'New')]
    body="""import sys
sys.path.insert(0,sys.argv[1])
from specroad.changes import TargetModel, TargetPolicy, prepare_change_target
from specroad.validation import ModelDocument
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
p=ProfileResource(%r)
effective=compose_profiles([p],core_key=p.key)
m=TargetModel(%r,ProjectReadBinding('sample','/provided',(1,2)),[ModelDocument(%r,%r)],
profile=effective,resource_files=[ModelDocument('profiles/core.json',p.source_bytes)])
r=prepare_change_target(m,%r,change_plan_id='CP',request_id='request',actor=%r,planned_at=%r,
scope_descriptor=%r,metadata_policy_version='change-metadata-v1',policy=TargetPolicy('change','1',()))
assert r.target_validated and r.artifacts[0]['statement']=='New'
assert r.artifacts[0]['revision']==2 and not r.transaction_prepared and not r.write_authorized
"""%(m.resource_files[0].content,m.configuration_bytes,m.documents[0].path,m.documents[0].content,ops,ACTOR,TIME,SCOPE)
    for location in (moved,movedzip):
        result=run_python(['-I','-S','-B','-c',body,str(location)],tmp_path,capture=True)
        assert result.returncode==0,result.stderr


def test_empty_target_still_executes_required_command_gates():
    m=model([]);seen=[]
    def check(c):seen.append(c.subjects);return c.result([{'reason':'command_blocked','severity':'error'}])
    r=prepare(m,[],gates=[gate(check=check)],policy=TargetPolicy('command','1',('extension:command',)))
    assert seen==[()] and not r.target_validated
    assert r.data['validation']['exit_code']==1


def test_empty_target_command_exceptions_are_not_silently_skipped():
    def check(c):raise RuntimeError('failure')
    r=prepare(model([]),[],gates=[gate(check=check)])
    assert not r.target_validated and r.data['validation']['exit_code']==4


def test_empty_target_old_command_result_still_has_plan_binding():
    stored=[]
    def check(c):
        if not stored:stored.append(c.result())
        return stored[0]
    m=model([]);g=gate(check=check)
    assert prepare(m,[],gates=[g]).target_validated
    assert not prepare(m,[],gates=[g],request_id='different').target_validated


def test_empty_target_incomplete_discovery_is_rejected():
    m=model([])
    g=ModelGate('extension:bad','1',lambda c:c.dependency_result({goal()['id']:[]}),lambda c:c.result())
    assert not prepare(m,[],gates=[g]).target_validated


def test_rule_resource_integrity_needs_explicit_service_even_without_artifacts():
    f=ModelDocument('rules/one.json',canonical_json_bytes({'schema_version':'0.2.0','rule_id':'one','version':'1.0.0','payload':1}))
    for artifacts in ([],[goal()]):
        m=model(artifacts,resource_files=[f])
        r=prepare(m,[])
        assert not r.target_validated and r.data['missing_command_gates']==['extension:target-resources']
        seen=[]
        def check(c):
            seen.append(c.resources_sha256)
            assert f in m.resource_files
            return c.result()
        assert prepare(m,[],gates=[gate('extension:target-resources',check=check)]).target_validated
        assert len(seen)==1 and len(seen[0])==64


def test_create_metadata_in_prepared_operations_must_match_plan_contract():
    # The target API takes prepared operations, not raw CLI draft fields.
    a=goal();m=model([])
    with pytest.raises(ModelError):prepare(m,[create(a)])
    a.update(created_at=TIME,updated_at=TIME,created_by=ACTOR,updated_by=ACTOR)
    r=prepare(m,[create(a)])
    assert r.target_validated and r.artifacts==[a]
