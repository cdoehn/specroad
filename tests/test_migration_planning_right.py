"""Changed sources, rehashed forgeries, mapping gaps and authority boundaries."""
import base64
import copy
import json
from pathlib import Path
from hashlib import sha256
from unittest.mock import patch
import pytest
from specroad.changes import ChangePlan, ChangePlanError, prepare_change_plan
from specroad.migration.planning import plan_migration, migration_inputs
from specroad.migration.plan_recheck import recheck_migration_plan
from specroad.migration.plan_values import MigrationPlanError
from support.migration_plans import FIELDS, target_inputs, mapped_inputs, planned_files, vector_source, unsigned
from support.reference01 import (minimal, full_project, finish_proposal, put, seal, encoded, digest)


def bound(files=None):
    files=vector_source() if files is None else files
    result=plan_migration(files,inputs=mapped_inputs(files),**FIELDS)
    plan=result.change_plan
    expected={'expected_target_version':'0.2.0',
        'expected_inputs_sha256':result.data['inputs_sha256'],'expected_plan_sha256':plan.sha256}
    return files,plan,expected


def rehash(value):
    value=copy.deepcopy(value);value.pop('change_plan_sha256',None)
    value['change_plan_sha256']=digest(value)
    return encoded(value)


def test_saved_plan_recheck_qualifies_real_source_and_rebuilds_every_target_byte():
    files,plan,expected=bound(full_project()); before=dict(files)
    result=recheck_migration_plan(plan.canonical_bytes,files,**expected)
    assert result.plan_sha256==plan.sha256
    assert result.target_model_root_sha256==plan.data['expected_result']['model_root_sha256']
    assert result.write_authorized is False and result.live_snapshot_atomic is False
    assert files==before
    with pytest.raises(TypeError): bool(result)


@pytest.mark.parametrize('change',['field','representation','addition','removal','archive'])
def test_every_real_source_byte_and_membership_change_is_stale(change):
    files,plan,expected=bound(full_project()); before=dict(files)
    if change=='field':
        value=json.loads(files['spec/requirements/SR-REQ-0001.json']);value['title']='Changed';put(files,value)
    elif change=='representation': files['spec/requirements/SR-REQ-0001.json']+=b'\n'
    elif change=='addition': files['notes.txt']=b'New unfiltered input'
    elif change=='removal': del files['spec/documents/SR-DOC-0001.json']
    else:
        name=next(n for n in files if n.startswith('archive/'));files[name]+=b'\n'
    changed=dict(files)
    with pytest.raises(MigrationPlanError) as error:recheck_migration_plan(plan.canonical_bytes,files,**expected)
    assert error.value.reason=='migration_source_files_changed' and error.value.exit_code==6
    assert files==changed and files!=before


@pytest.mark.parametrize('key,value',[
    ('expected_target_version','0.3.0'),('expected_inputs_sha256','0'*64),('expected_plan_sha256','0'*64)])
def test_request_expectations_are_external_to_the_saved_plan(key,value):
    files,plan,expected=bound();expected[key]=value
    with pytest.raises(MigrationPlanError) as error:recheck_migration_plan(plan.canonical_bytes,files,**expected)
    assert error.value.exit_code==6


def test_outer_self_hash_alone_does_not_accept_changed_request_metadata():
    files,plan,expected=bound();value=plan.data;value['actor']['actor_id']='substituted actor'
    with pytest.raises(MigrationPlanError,match='migration_plan_request_changed'):
        recheck_migration_plan(rehash(value),files,**expected)


def test_rehashed_result_forgery_fails_native_recomputation_even_if_self_hash_is_known():
    files,plan,expected=bound();value=plan.data;op=value['operations'][0]
    path='spec/requirements/SR-REQ-0001.json'
    row=next(c for c in op['changes'] if c['path']==path)
    target=json.loads(base64.b64decode(row['after_bytes_base64']));target['title']='Unauthorized substitution'
    raw=encoded(target);row['after_bytes_base64']=base64.b64encode(raw).decode();row['after_sha256']=sha256(raw).hexdigest()
    file_row=next(r for r in op['target_files'] if r['path']==path);file_row.update(size=len(raw),sha256=row['after_sha256'])
    artifact=next(r for r in value['result_artifacts'] if r['artifact']['id']=='SR-REQ-0001')
    artifact.update(artifact=target,sha256=digest(target))
    manifest=op['target_manifest'];record=next(r for r in manifest['artifacts'] if r['id']=='SR-REQ-0001');record['sha256']=digest(target)
    manifest['scope_sha256']=digest({k:v for k,v in manifest.items() if k not in ('model_manifest_version','scope_sha256')})
    op['target_model_root_sha256']=digest(manifest);value['expected_result']['model_root_sha256']=digest(manifest)
    raw=rehash(value);forged=ChangePlan(raw);expected['expected_plan_sha256']=forged.sha256
    with pytest.raises(MigrationPlanError,match='migration_native_plan_mismatch'):
        recheck_migration_plan(raw,files,**expected)


@pytest.mark.parametrize('mutation',['target_contract','step','direction','source_contract','result_root','input_hash','protected'])
def test_serialized_path_and_target_bindings_cannot_be_relabelled(mutation):
    files,plan,expected=bound(full_project());value=plan.data;op=value['operations'][0]
    if mutation=='target_contract':
        op['target_contract']['contract_sha256']='0'*64;op['steps'][0]['target_contract']['contract_sha256']='0'*64
    elif mutation=='step':op['steps'][0]['step_id']='other.v1'
    elif mutation=='direction':op['steps'][0]['direction']='backward'
    elif mutation=='source_contract':op['source_contract']['contract_sha256']='0'*64
    elif mutation=='result_root':value['expected_result']['model_root_sha256']='0'*64
    elif mutation=='input_hash':op['inputs_sha256']='0'*64
    else:op['protected_paths']=[]
    raw=rehash(value);expected['expected_plan_sha256']=json.loads(raw)['change_plan_sha256']
    with pytest.raises(MigrationPlanError):recheck_migration_plan(raw,files,**expected)


@pytest.mark.parametrize('value',[None,False,'', 'a'*63, 'A'*64, '0'*64+'\n'])
def test_expected_digest_contract_requires_an_actual_full_lowercase_hash(value):
    files,plan,expected=bound();expected['expected_inputs_sha256']=value
    with pytest.raises(MigrationPlanError,match='migration_expected_hash_required'):
        recheck_migration_plan(plan.canonical_bytes,files,**expected)


@pytest.mark.parametrize('field',['language','normative_force','statement'])
def test_required_mapping_fields_never_fall_back_to_source_text_or_locale(field):
    files=vector_source();inputs=target_inputs(files);del inputs['requirement_mappings'][0][field]
    with pytest.raises(MigrationPlanError):plan_migration(files,inputs=inputs,**FIELDS)


@pytest.mark.parametrize('change',['duplicate','unknown','extra','wrong_type'])
def test_mapping_identity_shape_and_scope_are_closed(change):
    files=vector_source();inputs=target_inputs(files)
    if change=='duplicate':inputs['requirement_mappings']*=2
    elif change=='unknown':inputs['requirement_mappings'][0]['artifact_id']='SR-REQ-9999'
    elif change=='extra':inputs['requirement_mappings'][0]['approved']=True
    else:inputs['requirement_mappings'][0]['language']=False
    with pytest.raises(MigrationPlanError):plan_migration(files,inputs=inputs,**FIELDS)


@pytest.mark.parametrize('path',['../escape.json','/absolute.json','.specroad/transactions/evil.json',
    '.git/config','profiles/../escape.json','profiles\\evil.json'])
def test_target_mapping_paths_cannot_select_code_or_operational_state(path):
    files=vector_source();inputs=target_inputs(files)
    inputs['target_resources']=[{'path':path,'bytes_base64':'e30='}]
    with pytest.raises(MigrationPlanError):plan_migration(files,inputs=inputs,**FIELDS)


def test_target_configuration_cannot_rename_project_identity():
    files=vector_source();inputs=target_inputs(files)
    config=json.loads(base64.b64decode(inputs['target_configuration']));config['project_id']='other'
    inputs['target_configuration']=base64.b64encode(encoded(config)).decode()
    with pytest.raises(MigrationPlanError,match='migration_project_mismatch'):
        plan_migration(files,inputs=inputs,**FIELDS)


def test_source_format_is_qualified_before_any_positive_plan():
    files=vector_source();inputs=target_inputs(files)
    value=json.loads(files['specroad.json']);value['source_contract']['contract_version']='9.0.0'
    files['specroad.json']=encoded(value)
    with pytest.raises(MigrationPlanError,match='unsupported_source_contract'):
        plan_migration(files,inputs=inputs,**FIELDS)


def test_original_revision_byte_conflict_cannot_be_hidden_by_equal_canonical_hash():
    files=full_project();seal(files,5)
    files['spec/requirements/SR-REQ-0001.json']+=b'\n'
    with pytest.raises(MigrationPlanError,match='migration_original_revision_conflict'):
        plan_migration(files,inputs=target_inputs(files),**FIELDS)


def test_old_approved_proposal_reviews_are_retained_but_do_not_approve_new_content():
    files=finish_proposal(full_project(),'approved');old=json.loads(files['spec/proposals/SR-PROP-0001.json'])
    result=plan_migration(files,inputs=mapped_inputs(files),**FIELDS)
    new=json.loads(planned_files(files,result.change_plan)['spec/proposals/SR-PROP-0001.json'])
    assert new['reviews']==old['reviews'] and new['control_history']==old['control_history']
    assert new['content_sha256']!=old['content_sha256'] and new['content_revision']==old['content_revision']+1
    assert new['proposal_status']==new['maturity']=='draft' and result.data['approval_granted'] is False
    assert all(row['binding']['content_sha256']!=new['content_sha256'] for row in new['reviews'])


def test_opaque_extensions_and_payloads_are_not_recursively_translated():
    files=vector_source();old=json.loads(files['spec/requirements/SR-REQ-0001.json'])
    opaque={'relation_locator':{'source_id':'SR-GOAL-0001','index':0},'schema_version':'0.1.0','command':'never-run'}
    old['extensions']['example.opaque']=opaque;put(files,old);files['unreferenced.bin']=b'\0\xffraw\r\n'
    result=plan_migration(files,inputs=target_inputs(files),**FIELDS);target=planned_files(files,result.change_plan)
    assert json.loads(target['spec/requirements/SR-REQ-0001.json'])['extensions']['example.opaque']==opaque
    assert target['unreferenced.bin']==files['unreferenced.bin']


def test_saved_plan_recheck_never_opens_a_writer_or_invokes_a_project_process():
    import subprocess,socket
    files,plan,expected=bound(full_project());before=dict(files)
    with patch.object(Path,'write_bytes',side_effect=AssertionError('write')), \
         patch.object(Path,'write_text',side_effect=AssertionError('write')), \
         patch.object(subprocess,'Popen',side_effect=AssertionError('process')), \
         patch.object(socket,'socket',side_effect=AssertionError('network')):
        result=recheck_migration_plan(plan.canonical_bytes,files,**expected)
    assert result.write_authorized is False and files==before


def test_old_approved_mutable_artifact_needs_new_approval_and_retains_its_old_bytes():
    files=minimal();old=json.loads(files['spec/goals/SR-GOAL-0001.json'])
    old.update(maturity='approved',success_criterion='Original bytes are preserved.');put(files,old)
    raw=files['spec/goals/SR-GOAL-0001.json']
    result=plan_migration(files,inputs=target_inputs(files),**FIELDS);target=planned_files(files,result.change_plan)
    current=json.loads(target['spec/goals/SR-GOAL-0001.json'])
    assert current['maturity']=='draft' and current['success_criterion']==old['success_criterion']
    h=sha256(raw).hexdigest();assert target['archive/objects/'+h[:2]+'/'+h]==raw
    assert result.data['approval_granted'] is False


def test_colliding_derived_relation_id_does_not_get_randomly_renamed(monkeypatch):
    import specroad.migration.planning as planning
    files=full_project()
    # Force the encoder boundary in trusted test code; data cannot register it.
    monkeypatch.setitem(planning._relation.__globals__,'encode128',lambda raw:'0'*26)
    with pytest.raises(MigrationPlanError,match='migration_relation_id_collision'):
        plan_migration(files,inputs=target_inputs(files),**FIELDS)


def test_timestamp_at_source_boundary_advances_by_one_microsecond_without_a_clock():
    files=vector_source();old=json.loads(files['spec/requirements/SR-REQ-0001.json'])
    old['updated_at']=FIELDS['planned_at'];put(files,old)
    result=plan_migration(files,inputs=target_inputs(files),**FIELDS)
    new=json.loads(planned_files(files,result.change_plan)['spec/requirements/SR-REQ-0001.json'])
    assert new['updated_at']=='2026-11-03T01:00:00.000001Z'
    assert new['revision']==2 and new['created_at']==old['created_at']


def test_physical_file_and_directory_collision_is_not_an_owned_snapshot():
    files=vector_source();files['notes']=b'x';files['notes/child']=b'y'
    with pytest.raises(MigrationPlanError,match='migration_path_overlap'):
        plan_migration(files,inputs=target_inputs(files),**FIELDS)
