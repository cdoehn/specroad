"""Working publication remains usable; unavailable release admission is closed."""
from dataclasses import FrozenInstanceError
import json
import shutil

import pytest

from specroad.archive import assess_release_baseline_readiness
from specroad.archive.creation import prepare_baseline_creation
from specroad.changes import ChangePlan, ChangeOperation
from specroad.changes._target_materialization import materialize_target
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.validation import ModelDocument
from support.domain import domain_value
from support.model import put
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import ref
from support.relations import aid
from test_baseline_creation import project, preview, plan_for, apply, ACTOR, TIME
from test_configured_baseline_right import variant_project


def release_project(root, *, policy=None):
    model=project(root)
    release=domain_value('release',readiness_policy={} if policy is None else policy)
    document=ModelDocument(artifact_path('release',release['id'],'SR'),canonical_json_bytes(release))
    model=materialize_target(model,(document,));put(root,document.path,document.content)
    return model,release


def prepare(model, **changes):
    options=dict(baseline_kind='working',baseline_id=ref('BASE'),name='Working snapshot',
        actor=ACTOR,planned_at=TIME,change_plan_id='CP-baseline',request_id='baseline-1')
    options.update(changes)
    return prepare_baseline_creation(model,**options)


@pytest.mark.parametrize('configured',[False,True])
def test_explicit_working_kind_preserves_the_existing_plan_and_native_publication(tmp_path,configured):
    root=tmp_path/'project';model=variant_project(root) if configured else project(root)
    options={'configuration_id':aid('configuration',2)} if configured else {}
    before=inventory(root)
    with no_write_attempts():
        current=prepare(model,**options);existing=preview(model,**options)
    assert current==existing and current['target_validated']
    assert inventory(root)==before
    plan=ChangePlan(canonical_json_bytes(current['plan']));result=apply(plan,model)
    assert result['write_state']=='committed' and result['completion']['current_target_verified']
    assert plan.data['operations'][0]['record']['baseline_kind']=='working'


@pytest.mark.parametrize('evaluation',[None,{}, {'selection':'stored-but-not-yet-evaluated'}])
def test_release_observation_binds_stored_policy_without_inventing_readiness(tmp_path,evaluation):
    policy={} if evaluation is None else {'verification_evaluation':evaluation}
    model,release=release_project(tmp_path/'project',policy=policy);before=inventory(tmp_path)
    with no_write_attempts():report=assess_release_baseline_readiness(model,release_id=release['id'])
    data=report.data
    assert data['release_id']==release['id'] and data['release_revision']==release['revision']
    assert data['release_sha256']==canonical_json_sha256(release)
    assert data['stored_evaluation_present']==(evaluation is not None)
    assert data['stored_evaluation_sha256']==(None if evaluation is None else canonical_json_sha256(evaluation))
    assert data['blockers']==([] if evaluation is not None else ['stored_release_evaluation_required'])+['release_readiness_provider_unavailable']
    assert not any(data[k] for k in ('ready','readiness_provider_available','readiness_evaluated',
        'stored_evaluation_validated','full_validation_passed','write_authorized','release_authorized'))
    assert inventory(tmp_path)==before


@pytest.mark.parametrize('policy',[{}, {'verification_evaluation':{}},
    {'verification_evaluation':{'required_runs':[]},'ready':True,'passed':True}])
def test_release_preparation_refuses_before_any_baseline_object_plan_or_transaction_is_created(tmp_path,policy):
    root=tmp_path/'project';model,release=release_project(root,policy=policy);before=inventory(root)
    with no_write_attempts(),pytest.raises(ModelError) as error:
        prepare(model,baseline_kind='release',release_id=release['id'])
    assert error.value.reason=='release_baseline_readiness_required'
    assert inventory(root)==before and not (root/'archive').exists()
    assert not (root/'spec/baselines').exists() and not (root/'.specroad/transactions').exists()


def test_detached_readiness_mutation_cannot_open_release_admission(tmp_path):
    model,release=release_project(tmp_path/'project');report=assess_release_baseline_readiness(model,release_id=release['id'])
    digest=report.sha256;data=report.data;data.update(ready=True,release_authorized=True,readiness_provider_available=True);data['blockers'].clear()
    assert report.sha256==digest and not report.data['ready']
    with pytest.raises(ModelError) as error:report.require_ready()
    assert error.value.reason=='release_baseline_readiness_required'
    with pytest.raises(TypeError):bool(report)
    with pytest.raises(FrozenInstanceError):report._encoded=b'{}'


def test_unavailable_gate_uses_supplied_bytes_without_current_tree_or_git(tmp_path):
    root=tmp_path/'project';model,release=release_project(root)
    before=assess_release_baseline_readiness(model,release_id=release['id']).data
    shutil.rmtree(root)
    with no_write_attempts():after=assess_release_baseline_readiness(model,release_id=release['id']).data
    assert after==before and not root.exists()


@pytest.mark.parametrize('identity',[None,'',ref('GOAL'),'OTHER-REL-'+'0'*26])
def test_release_gate_requires_an_explicit_matching_release_identity(tmp_path,identity):
    model,_=release_project(tmp_path/'project')
    with no_write_attempts(),pytest.raises(ModelError) as error:
        assess_release_baseline_readiness(model,release_id=identity)
    assert error.value.reason=='artifact_identity_mismatch'


def test_missing_release_cannot_select_a_different_existing_release(tmp_path):
    model,_=release_project(tmp_path/'project');missing=ref('REL','1')
    with no_write_attempts(),pytest.raises(ModelError) as error:
        assess_release_baseline_readiness(model,release_id=missing)
    assert error.value.reason=='baseline_release_missing'
    assert error.value.path==artifact_path('release',missing,'SR')


@pytest.mark.parametrize('kind',[None,True,'RELEASE','snapshot'])
def test_unknown_baseline_kind_cannot_fall_back_to_working_creation(tmp_path,kind):
    model=project(tmp_path/'project');before=inventory(tmp_path)
    with no_write_attempts(),pytest.raises(ModelError) as error:prepare(model,baseline_kind=kind)
    assert error.value.reason=='baseline_kind_invalid' and inventory(tmp_path)==before


def test_release_selector_cannot_be_silently_ignored_for_a_working_request(tmp_path):
    model=project(tmp_path/'project')
    with no_write_attempts(),pytest.raises(ModelError) as error:prepare(model,release_id=ref('REL'))
    assert error.value.reason=='working_baseline_release_selection_not_applicable'


def test_relabeling_a_prepared_working_operation_keeps_the_existing_release_boundary_closed(tmp_path):
    model=project(tmp_path/'project');operation=plan_for(model).data['operations'][0]
    operation['record']['baseline_kind']='release'
    with no_write_attempts(),pytest.raises(ModelError) as error:ChangeOperation(operation)
    assert error.value.reason=='release_baseline_readiness_required'
    assert error.value.pointer=='/record/baseline_kind'


@pytest.mark.parametrize('mode',['core','pyz'])
def test_release_observation_runs_in_isolated_core_and_pyz_without_native_services(tmp_path,mode):
    root=tmp_path/'project';model,release=release_project(root)
    code='''from specroad.archive import assess_release_baseline_readiness
from specroad.changes import TargetModel
from specroad.model.canonical import canonical_json_bytes
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.language_registry import LanguageRegistry
from specroad.profiles import ProfileResource,compose_profiles
from specroad.validation import ModelDocument
from specroad.model.errors import ModelError
'''
    code+='configuration='+repr(model.configuration.data)+'\n'
    code+='documents='+repr([(d.path,d.content) for d in model.documents])+'\n'
    code+='resources='+repr([(d.path,d.content) for d in model.resource_files])+'\n'
    code+='''mapping=dict(resources);data=configuration['language_registry']
registry=LanguageRegistry(mapping[data['path']],expected_sha256=data['sha256'],expected_version=data['registry_version'])
profile=ProfileResource(mapping['profiles/core.json'])
model=TargetModel(canonical_json_bytes(configuration),ProjectReadBinding(configuration['project_id'],'supplied',(0,0)),
    [ModelDocument(p,b) for p,b in documents],profile=compose_profiles([profile],core_key=profile.key,language_registry=registry),
    resource_files=[ModelDocument(p,b) for p,b in resources])
'''
    code+='report=assess_release_baseline_readiness(model,release_id='+repr(release['id'])+')\n'
    code+='''assert not report.data['ready'] and not report.data['release_authorized']
try:report.require_ready()
except ModelError as error:assert error.reason=='release_baseline_readiness_required'
else:raise AssertionError('Unavailable release gate passed')
'''
    if mode=='core':result=run_core(code,tmp_path,capture=True)
    else:
        _,package=build_distribution(tmp_path/'distribution')
        result=run_python(['-I','-S','-B','-c','import sys;sys.path.insert(0,'+repr(str(package))+')\n'+code],tmp_path,capture=True)
    assert result.returncode==0,result.stderr
