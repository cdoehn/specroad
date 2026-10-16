"""Native variant publication and independent historical selection integrity."""
from base64 import b64decode
import json
import shutil

import pytest

from specroad.archive import verify_baseline_objects, compare_baselines
from specroad.archive.objects import SnapshotObject
from specroad.archive.project_snapshot import build_project_baseline_manifest
from specroad.changes import ChangePlan
from specroad.changes._target_materialization import materialize_target
from specroad.changes.baselines import prepare_baseline_operation, object_documents
from specroad.configurations import resolve_configuration
from specroad.graph.relations import SourceRelations
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.query import ComparisonSourceSnapshot, compare_sources
from specroad.validation import ModelDocument
from support.model import put
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import ref
from support.relations import aid, edge
from test_baseline_creation import project, preview, apply, ACTOR, TIME
from test_baseline_materialization import restore, show
from test_baseline_verification import verify, row_for, replace_object
from test_configured_baseline import variant_values


def document(value):
    return ModelDocument(artifact_path(value['artifact_type'], value['id'], 'SR'),
                         canonical_json_bytes(value))


def variant_project(root, *, values=None):
    model = project(root)
    values = variant_values() if values is None else values
    model = materialize_target(model, tuple(document(v) for v in values))
    for path, raw in model.source_files.items(): put(root, path, raw)
    return model


def prepared(model, *, selected=2, number='0'):
    return prepare_baseline_operation(model, baseline_id=ref('BASE', number),
        name='Historical variant', actor=ACTOR, planned_at=TIME,
        configuration_id=aid('configuration', selected))


def stored_variant(root, model, **options):
    operation = prepared(model, **options)
    root.mkdir()
    for item in operation['objects']: put(root, item['path'], b64decode(item['bytes_base64']))
    record = operation['record']
    put(root, artifact_path('baseline', record['id'], 'SR'), canonical_json_bytes(record))
    return record, operation


@pytest.mark.parametrize('selected,platform', [(1,'linux'), (2,'windows')])
def test_native_configured_creation_keeps_full_current_tree_and_archives_only_selected_artifacts(tmp_path, selected, platform):
    root=tmp_path/'project'; model=variant_project(root)
    before=dict(model.source_files)
    with no_write_attempts(): value=preview(model, configuration_id=aid('configuration',selected))
    assert value['target_validated'], json.dumps(value['diagnostics'],indent=2)
    plan=ChangePlan(canonical_json_bytes(value['plan'])); result=apply(plan,model)
    record=plan.data['operations'][0]['record']
    report=verify(root,record)
    effective=resolve_configuration(tuple(SourceRelations(d.content) for d in model.documents),
                                    aid('configuration',selected))
    assert report['configuration_binding']==effective.binding
    assert row_for(record,'effective_configuration')['configuration_id']==effective.configuration_id
    assert json.loads((root/row_for(record,'effective_configuration')['object_path']).read_bytes())['effective_values']=={'platform':platform}
    assert {r['id'] for r in record['manifest'] if r['role']=='artifact'}=={
        ref('GOAL'),aid('goal'),aid('configuration'),aid('configuration',2),aid(number=selected)}
    assert all((root/p).read_bytes()==raw for p,raw in before.items())
    assert result['write_state']=='committed' and result['completion']['current_target_verified']
    assert not report['full_validation_passed'] and not report['release_authorized']


@pytest.mark.parametrize('change', ['parent_revision','parent_selection','child_revision','child_selection'])
def test_original_variant_remains_verifiable_when_current_chain_changes_and_sources_disappear(tmp_path, change):
    original=tmp_path/'original'; model=variant_project(original)
    root=tmp_path/'archive'; record,operation=stored_variant(root,model)
    first=verify(root,record); values=variant_values()
    if change=='parent_revision': values[0]['revision']+=1
    elif change=='parent_selection': values[0]['selection']['platform']='windows'
    elif change=='child_revision': values[1]['revision']+=1
    else: values[1]['selection']['platform']='linux'
    changed=materialize_target(model,tuple(document(v) for v in values))
    newer=build_project_baseline_manifest(changed,baseline_id=ref('BASE','1'),configuration_id=aid('configuration',2))
    for path,raw in changed.source_files.items(): put(root,path,raw)
    assert newer.data['configuration_binding']['sha256']!=first['configuration_binding']['sha256']
    assert newer.model_root_sha256!=first['model_root_sha256']
    shutil.rmtree(original); before=inventory(root)
    with no_write_attempts():
        assert verify(root,record)==first
        view=show(root,record)
        supplied=verify_baseline_objects(canonical_json_bytes(record),
            tuple(SnapshotObject(b64decode(o['bytes_base64'])) for o in operation['objects']))
    assert supplied==first and view['integrity']['verification']==first
    assert inventory(root)==before


@pytest.mark.parametrize('failure', ['missing','changed','rebound'])
def test_selection_object_cannot_be_replaced_by_current_configuration_or_a_hash_label(tmp_path, failure):
    model=variant_project(tmp_path/'original'); root=tmp_path/'archive'
    record,_=stored_variant(root,model); row=row_for(record,'effective_configuration')
    path=root/row['object_path']; raw=path.read_bytes()
    for name,content in model.source_files.items(): put(root,name,content)
    if failure=='missing': path.unlink()
    elif failure=='changed': path.write_bytes(raw.replace(b'windows',b'unknown'))
    else:
        value=json.loads(raw); value['effective_values']['platform']='linux'
        replace_object(root,row,canonical_json_bytes(value))
    expected={'missing':'snapshot_referenced_object_missing','changed':'snapshot_object_hash_mismatch',
              'rebound':'baseline_snapshot_manifest_mismatch'}[failure]
    before=inventory(root)
    with no_write_attempts(),pytest.raises(ModelError) as error: verify(root,record)
    assert error.value.reason==expected and inventory(root)==before
    assert show(root,record)['integrity']['status']=='failed'


@pytest.mark.parametrize('field,value', [('configuration_id',aid('configuration')),
                                        ('configuration_revision',99)])
def test_selection_row_metadata_must_match_actual_archived_chain(tmp_path, field, value):
    model=variant_project(tmp_path/'original'); root=tmp_path/'archive'
    record,_=stored_variant(root,model); row_for(record,'effective_configuration')[field]=value
    with no_write_attempts(),pytest.raises(ModelError) as error: verify(root,record)
    assert error.value.reason=='baseline_snapshot_manifest_mismatch'


def test_selection_scope_cannot_be_rebound_to_another_retained_variant(tmp_path):
    model=variant_project(tmp_path/'original'); root=tmp_path/'archive'
    record,_=stored_variant(root,model); record['scope_descriptor']['configuration_id']=aid('configuration')
    with no_write_attempts(),pytest.raises(ModelError) as error: verify(root,record)
    assert error.value.reason=='baseline_model_root_mismatch'


@pytest.mark.parametrize('member', [1,2])
def test_missing_actual_chain_object_never_uses_current_source_bytes(tmp_path, member):
    model=variant_project(tmp_path/'original'); root=tmp_path/'archive'; record,_=stored_variant(root,model)
    row=next(r for r in record['manifest'] if r.get('id')==aid('configuration',member))
    put(root,row['source_path'],(root/row['object_path']).read_bytes()); (root/row['object_path']).unlink()
    with no_write_attempts(),pytest.raises(ModelError) as error: verify(root,record)
    assert error.value.reason=='snapshot_referenced_object_missing'


def test_native_closed_variant_rejects_an_excluded_required_dependency(tmp_path):
    values=variant_values(); values[3]['relations']=[edge('depends_on',aid(number=2))]
    model=variant_project(tmp_path/'original',values=values); before=inventory(tmp_path)
    with no_write_attempts(),pytest.raises(ModelError) as error: prepared(model,selected=1)
    assert error.value.reason=='baseline_configuration_dependency_excluded' and inventory(tmp_path)==before


def test_native_selection_gate_cannot_be_replaced_by_a_caller_success_stub(tmp_path):
    from specroad.validation import ModelGate
    model=variant_project(tmp_path/'project')
    fake=ModelGate('configuration','fake',lambda c:c.dependency_result({n:list(c.all_ids) for n in c.subjects}),
                   lambda c:c.result())
    before=inventory(tmp_path)
    with no_write_attempts(),pytest.raises(ModelError) as error:
        preview(model,configuration_id=aid('configuration',2),gates=(fake,))
    assert error.value.reason=='target_distinct_registered_gates_required' and inventory(tmp_path)==before


def test_native_closed_variant_does_not_silently_drop_a_weak_relation_to_an_excluded_target(tmp_path):
    values=variant_values(); values[3]['relations']=[edge('conflicts_with',aid(number=2))]
    model=variant_project(tmp_path/'original',values=values)
    with no_write_attempts(),pytest.raises(ModelError) as error:prepared(model,selected=1)
    assert error.value.reason=='missing_relation_target'
    assert error.value.pointer=='/relations/0/target'


@pytest.mark.parametrize('selected',[1,2])
def test_shared_configured_project_preparation_uses_the_same_historical_snapshot_reader(tmp_path,selected):
    from specroad.archive import build_baseline_manifest
    from support.records import record_value
    from test_configured_baseline import variant_inputs
    snapshot=build_baseline_manifest(**variant_inputs(selected=selected),baseline_id=ref('BASE'))
    record=record_value('baseline',**{k:snapshot.data[k] for k in (
        'scope_descriptor','manifest','model_root_sha256','configuration_hash','profiles','tool_version')})
    root=tmp_path/'archive';root.mkdir()
    for item in snapshot.objects:put(root,item.reference.path,item.content)
    with no_write_attempts():report=verify(root,record)
    assert report['model_root_sha256']==snapshot.model_root_sha256
    assert report['configuration_binding']==snapshot.data['configuration_binding']


def test_excluded_existing_baseline_identity_is_still_reserved_before_selection(tmp_path):
    model=variant_project(tmp_path/'original'); operation=prepared(model)
    record=operation['record']
    from test_configuration_scope import condition
    record['applicability']=condition('linux')
    model=materialize_target(model,(document(record),*object_documents(operation)))
    with no_write_attempts(),pytest.raises(ModelError) as error: prepared(model)
    assert error.value.reason=='baseline_identity_already_present'


def test_excluded_older_baseline_does_not_add_its_archived_objects_to_selected_snapshot(tmp_path):
    model=variant_project(tmp_path/'original'); operation=prepared(model)
    record=operation['record']
    from test_configuration_scope import condition
    record['applicability']=condition('linux')
    model=materialize_target(model,(document(record),*object_documents(operation)))
    root=tmp_path/'archive'; selected,_=stored_variant(root,model,number='1')
    assert not any(r['role']=='archive' for r in selected['manifest'])
    assert record['id'] not in {r.get('id') for r in selected['manifest']}
    assert verify(root,selected)['snapshot_integrity_verified']


def test_retained_older_baseline_keeps_its_exact_archived_objects(tmp_path):
    model=variant_project(tmp_path/'original'); operation=prepared(model)
    model=materialize_target(model,(document(operation['record']),*object_documents(operation)))
    root=tmp_path/'archive'; record,_=stored_variant(root,model,number='1')
    assert {r['source_path'] for r in record['manifest'] if r['role']=='archive'}=={
        o['path'] for o in operation['objects']}
    assert verify(root,record)['snapshot_integrity_verified']


def test_materialization_restores_historical_selection_and_exact_variant_after_source_removal(tmp_path):
    original=tmp_path/'original'; model=variant_project(original)
    root=tmp_path/'archive'; record,_=stored_variant(root,model); shutil.rmtree(original)
    expected=verify(root,record); target=tmp_path/'restored'
    report=restore(root,record,target)
    assert report['configuration_binding']==expected['configuration_binding']
    assert report['model_root_sha256']==expected['model_root_sha256'] and report['materialization_complete']
    assert not (target/artifact_path('requirement',aid(),'SR')).exists()
    assert (target/artifact_path('requirement',aid(number=2),'SR')).is_file()
    records=tuple(SourceRelations((target/r['source_path']).read_bytes())
                  for r in record['manifest'] if r['role']=='artifact')
    assert resolve_configuration(records,aid('configuration',2)).binding==expected['configuration_binding']
    assert not report['full_validation_passed'] and not report['release_authorized']


def test_two_historical_variant_sources_keep_bindings_and_shared_comparison_contract(tmp_path):
    original=tmp_path/'original'; model=variant_project(original)
    left=tmp_path/'left'; first,_=stored_variant(left,model,selected=1)
    right=tmp_path/'right'; second,_=stored_variant(right,model,selected=2,number='1')
    shutil.rmtree(original); before=inventory(tmp_path)
    with no_write_attempts():
        a=ComparisonSourceSnapshot(left,kind='baseline',reference=first['id'])
        b=ComparisonSourceSnapshot(right,kind='baseline',reference=second['id'])
        actual=compare_baselines(left,first['id'],right,canonical_json_bytes(second))
        expected=compare_sources(a,b)
    assert actual.data==expected.data and actual.sha256==expected.sha256
    assert actual.data['inventory_delta']['removed_ids']==[aid()]
    assert actual.data['inventory_delta']['added_ids']==[aid(number=2)]
    assert a.binding['baseline']['configuration_binding']==verify(left,first)['configuration_binding']
    assert b.binding['baseline']['configuration_binding']==verify(right,second)['configuration_binding']
    assert inventory(tmp_path)==before


@pytest.mark.parametrize('mode',['core','pyz'])
def test_historical_configured_verification_runs_in_isolated_core_and_pyz(tmp_path,mode):
    model=variant_project(tmp_path/'original'); root=tmp_path/'archive'; record,_=stored_variant(root,model)
    code='from pathlib import Path\nfrom specroad.archive import verify_baseline_snapshot\nfrom specroad.security import ProjectBoundary\n'
    code+='result=verify_baseline_snapshot(ProjectBoundary(Path('+repr(str(root))+')),'+repr(canonical_json_bytes(record))+')\n'
    code+='assert result["snapshot_integrity_verified"] and result["configuration_binding"]["configuration_id"]=='+repr(aid('configuration',2))+'\n'
    code+='assert not result["full_validation_passed"] and not result["release_authorized"]\n'
    if mode=='core': result=run_core(code,tmp_path,capture=True)
    else:
        _,package=build_distribution(tmp_path/'distribution')
        result=run_python(['-I','-S','-B','-c','import sys;sys.path.insert(0,'+repr(str(package))+')\n'+code],tmp_path,capture=True)
    assert result.returncode==0,result.stderr
