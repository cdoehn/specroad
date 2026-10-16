"""Stored variant selection, actual parent-chain bytes and scoped manifests."""
from dataclasses import FrozenInstanceError
import json
import shutil

import pytest

from specroad.archive import build_baseline_manifest, SnapshotObjectStore
from specroad.archive.objects import ObjectReference, read_snapshot_object
from specroad.configurations import resolve_configuration
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_admission import ScopeConfigurationDependencyError
from specroad.graph.scope_hash import fingerprint_scope
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.manifest_resources import project_json_resource
from specroad.model.semantic_configuration import semantic_configuration
from specroad.security import ProjectBoundary
from support.domain import domain_value
from support.model import put, configuration_value
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import ref
from support.relations import aid, edge
from support.scopes import descriptor
from test_baseline_manifest import baseline_inputs
from test_configuration_scope import configuration, condition


def variant_values():
    parent = configuration()
    child = configuration(2, parent=parent['id'], dimensions=[], selection={'platform':'windows'})
    return [parent, child, domain_value('goal', id=aid('goal')),
            domain_value('requirement', id=aid(), applicability=condition('linux')),
            domain_value('requirement', id=aid(number=2), applicability=condition('windows'))]


def variant_inputs(*, selected=1, wrapper=False, values=None, scope=None, **changes):
    if scope is None:
        scope = (descriptor('configuration', {'base_scope_descriptor':descriptor('project')},
                            configuration_id=aid('configuration', selected)) if wrapper else
                 descriptor('project', configuration_id=aid('configuration', selected)))
    return baseline_inputs(values=variant_values() if values is None else values,
                           scope=scope, attachment=None, **changes)


def selection_snapshot(snapshot):
    row = next(r for r in snapshot.data['manifest'] if r['role']=='effective_configuration')
    content = next(o.content for o in snapshot.objects if o.reference.path==row['object_path'])
    return row, json.loads(content)


@pytest.mark.parametrize('wrapper', [False, True])
def test_two_variant_snapshots_retain_exact_selection_and_resulting_artifact_scope(wrapper):
    snapshots = []
    for selected, platform in ((1,'linux'),(2,'windows')):
        args = variant_inputs(selected=selected, wrapper=wrapper)
        with no_write_attempts(): snapshot = build_baseline_manifest(**args, baseline_id=ref('BASE',str(selected)))
        snapshots.append(snapshot); data=snapshot.data
        effective = resolve_configuration(args['dependencies'].inventory.records, aid('configuration',selected))
        assert data['configuration_binding']==effective.binding
        row, stored = selection_snapshot(snapshot)
        assert stored==effective.manifest and stored['effective_values']=={'platform':platform}
        assert row['sha256']==effective.sha256 and row['configuration_revision']==effective.data['configuration_revision']
        assert data['scope_descriptor']==args['closure'].seeds.descriptor.data
        assert {r['id'] for r in data['manifest'] if r['role']=='artifact'}=={
            aid('configuration'),aid('configuration',2),aid('goal'),aid(number=selected)}
        resources={name:project_json_resource(args['configuration'],path,raw,args['binding'])
                   for name,(path,raw) in args['resource_payloads'].items()}
        expected=fingerprint_scope(args['configuration'],args['binding'],args['closure'],args['dependencies'],
            effective_profile=args['effective_profile'].data,resource_records=resources)
        assert data['model_manifest']==expected.data and snapshot.model_root_sha256==expected.sha256
        assert data['configuration_hash']==canonical_json_sha256(semantic_configuration(args['configuration']))
        assert data['model_manifest']['configuration_sha256']==effective.scope_sha256(args['configuration'])
        assert not any(snapshot.assurance[k] for k in ('full_validation_passed','write_authorized','release_authorized'))
    assert snapshots[0].model_root_sha256!=snapshots[1].model_root_sha256


@pytest.mark.parametrize('change', ['parent_revision','parent_selection','child_revision','child_selection'])
def test_new_parent_or_selection_bytes_change_the_new_binding_without_changing_the_saved_snapshot(change):
    values=variant_values(); original=build_baseline_manifest(**variant_inputs(selected=2,values=values))
    saved=original.canonical_bytes
    if change=='parent_revision': values[0]['revision']+=1
    elif change=='parent_selection': values[0]['selection']['platform']='windows'
    elif change=='child_revision': values[1]['revision']+=1
    else: values[1]['selection']['platform']='linux'
    changed=build_baseline_manifest(**variant_inputs(selected=2,values=values))
    assert original.canonical_bytes==saved
    assert original.data['configuration_binding']['sha256']!=changed.data['configuration_binding']['sha256']
    assert original.model_root_sha256!=changed.model_root_sha256


def test_archived_configuration_selection_can_be_resolved_from_stored_objects_without_original_files(tmp_path):
    original=tmp_path/'original';original.mkdir()
    args=variant_inputs(selected=2);snapshot=build_baseline_manifest(**args,baseline_id=ref('BASE'))
    for source in args['dependencies'].inventory.records:put(original,source.identity.id+'.json',source.source_bytes)
    archive=tmp_path/'archive';archive.mkdir(mode=0o700)
    store=SnapshotObjectStore(archive,protected_roots=(ProjectBoundary(original),))
    for item in snapshot.objects:store.put(item)
    put(archive,'manifest.json',snapshot.canonical_bytes)
    expected=snapshot.data['configuration_binding'];del snapshot
    shutil.rmtree(original);before=inventory(archive)
    with no_write_attempts():
        stored=json.loads((archive/'manifest.json').read_bytes());boundary=ProjectBoundary(archive)
        records=[SourceRelations(read_snapshot_object(boundary,ObjectReference(r['sha256'],r['size'])))
                 for r in stored['manifest'] if r['role']=='artifact']
        selection=resolve_configuration(records,stored['configuration_binding']['configuration_id'])
        row=next(r for r in stored['manifest'] if r['role']=='effective_configuration')
        actual=read_snapshot_object(boundary,ObjectReference(row['sha256'],row['size']))
    assert selection.binding==expected and canonical_json_bytes(selection.manifest)==actual
    assert selection.effective_values=={'platform':'windows'} and inventory(archive)==before


@pytest.mark.parametrize('included', [[], [aid('configuration',2)]])
def test_configured_snapshot_refuses_a_scope_that_omits_actual_selection_chain_records(included):
    scope=descriptor('explicit',{'artifact_ids':sorted([aid('goal'),*included]),
        'resource_ids':['mapping:exchange','profile:core','profile:product','rule:check']},
        configuration_id=aid('configuration',2))
    args=variant_inputs(selected=2,scope=scope)
    with no_write_attempts(),pytest.raises(ModelError) as error:build_baseline_manifest(**args)
    assert error.value.reason=='baseline_configuration_chain_not_retained'


def test_unconfigured_snapshot_preserves_its_original_contract_without_selection_metadata():
    args=baseline_inputs(attachment=None,scope=descriptor('project'))
    snapshot=build_baseline_manifest(**args)
    assert 'configuration_binding' not in snapshot.data
    assert 'effective_configuration' not in {r['role'] for r in snapshot.data['manifest']}
    assert snapshot.data['configuration_hash']==snapshot.data['model_manifest']['configuration_sha256']


def test_configured_snapshot_is_independent_of_input_order():
    a=build_baseline_manifest(**variant_inputs(selected=2))
    b=build_baseline_manifest(**variant_inputs(selected=2,reverse=True))
    assert a.canonical_bytes==b.canonical_bytes and a.objects==b.objects


@pytest.mark.parametrize('operational', [{'default_locale':'de-DE'},{'generated_path':'rendered'}])
def test_operational_project_choices_do_not_change_the_stored_variant(operational):
    first=build_baseline_manifest(**variant_inputs(selected=2))
    second=build_baseline_manifest(**variant_inputs(selected=2,configuration=configuration_value(**operational)))
    assert first.canonical_bytes==second.canonical_bytes and first.objects==second.objects


@pytest.mark.parametrize('resource', ['profile:core','profile:product','rule:check','mapping:exchange'])
def test_selected_configuration_never_licenses_an_incomplete_resource_snapshot(resource):
    args=variant_inputs(selected=2);del args['resource_payloads'][resource]
    with no_write_attempts(),pytest.raises(ModelError) as error:build_baseline_manifest(**args)
    assert error.value.reason=='baseline_resource_payload_set_mismatch'


def test_owned_selection_metadata_cannot_mutate_the_baseline_manifest():
    snapshot=build_baseline_manifest(**variant_inputs(selected=2));raw=snapshot.canonical_bytes
    snapshot.data['configuration_binding']['sha256']='0'*64
    row,value=selection_snapshot(snapshot);value['effective_values']['platform']='linux';row.clear()
    assert snapshot.canonical_bytes==raw and selection_snapshot(snapshot)[1]['effective_values']=={'platform':'windows'}
    with pytest.raises(FrozenInstanceError):snapshot.objects=()


def test_excluded_required_dependency_prevents_variant_baseline_preparation():
    values=variant_values();values[3]['relations']=[edge('depends_on',aid(number=2))]
    with no_write_attempts(),pytest.raises(ScopeConfigurationDependencyError):
        build_baseline_manifest(**variant_inputs(values=values))


@pytest.mark.parametrize('mode',['core','pyz'])
def test_variant_snapshot_preparation_runs_in_isolated_core_and_pyz(tmp_path,mode):
    args=variant_inputs(selected=2)
    data={'configuration':args['configuration'].data,
          'records':[r.source_bytes.decode() for r in args['dependencies'].inventory.records],
          'resources':[r.data for r in args['dependencies'].inventory.resources],
          'payloads':{k:[p,raw.decode()] for k,(p,raw) in args['resource_payloads'].items()},
          'scope':args['closure'].seeds.descriptor.data}
    code='''import json
from specroad.archive import build_baseline_manifest
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_inputs import ScopeSeedInputs,ScopeResource
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_seeds import resolve_scope_seeds
from specroad.graph.scope_closure import resolve_scope_closure
from specroad.graph.closure_inputs import ClosureBindings,artifact_node,resource_node
from specroad.model.configuration import ProjectConfiguration
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource,compose_profiles
'''
    code+='data=json.loads('+repr(json.dumps(data))+')\n'
    code+='''configuration=ProjectConfiguration(data['configuration'])
records=[SourceRelations(r.encode()) for r in data['records']]
resources=[ScopeResource(**r) for r in data['resources']]
inventory=ScopeSeedInputs(configuration,records,resources)
uses={artifact_node(r.identity.id):[] for r in records}
uses.update({resource_node(r.resource_id):[] for r in resources})
dependencies=ClosureBindings(inventory,uses=uses,current_reviews={})
closure=resolve_scope_closure(resolve_scope_seeds(ScopeDescriptor(data['scope']),inventory),dependencies)
payloads={k:(p,raw.encode()) for k,(p,raw) in data['payloads'].items()}
profiles=[ProfileResource(raw) for k,(p,raw) in payloads.items() if k.startswith('profile:')]
profile=compose_profiles(profiles,core_key=profiles[0].key,project_profiles=[profiles[1].key])
snapshot=build_baseline_manifest(configuration,ProjectReadBinding(configuration.project_id,'isolated',(0,0)),
    closure,dependencies,baseline_kind='working',effective_profile=profile,
    resource_payloads=payloads,attachment_payloads={})
assert snapshot.data['configuration_binding']['configuration_id']==data['scope']['configuration_id']
assert any(r['role']=='effective_configuration' for r in snapshot.data['manifest'])
assert not snapshot.assurance['write_authorized']
'''
    if mode=='core':result=run_core(code,tmp_path,capture=True)
    else:
        _,package=build_distribution(tmp_path/'distribution')
        result=run_python(['-I','-S','-B','-c','import sys;sys.path.insert(0,'+repr(str(package))+')\n'+code],tmp_path,capture=True)
    assert result.returncode==0,result.stderr
