"""17.g.R: source rebuild, missing/null/binary boundaries and passive CLI errors."""
from copy import deepcopy
from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from specroad.merge import build_merge_conflicts, parse_merge_conflicts, read_merge_conflicts
from specroad.merge.sources import SourceSnapshot
from specroad.model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from specroad.model.errors import ModelError
from specroad.cli.application import dispatch_result
from specroad.cli.results import thaw
from specroad.security import ProjectBoundary
from support.merge_lifecycle import artifact, bound_records, changed
from support.merge_relations import history_for, bound_relations, edge
from support.records import record_value
from support.read_only import inventory
from test_merge_inventory import bind_files
from test_project_bundle import project
from test_merge_conflicts import catalogue, PLAN_ID, ROLES


@pytest.fixture(scope='module')
def original(tmp_path_factory):
    return project(tmp_path_factory.mktemp('conflict-right-seed')/'project').raw


@pytest.fixture
def bound(tmp_path,original):
    path,value=artifact(original)
    (tmp_path/'sources').mkdir()
    sources,history=bound_records(tmp_path/'sources',original,path,[changed(value,title=r) for r in ROLES])
    return sources,history,catalogue(sources,history)


def rehash(document):
    document['source_bindings_sha256']=digest(document['source_bindings'])
    for row in document['conflicts']:
        seed={name:document[name] for name in ('conflict_format_version','plan_id','source_bindings_sha256','history_input_sha256')}
        seed.update({name:row[name] for name in ('identity','pointer','conflict_class','element_keys')})
        row['conflict_id']='MC-'+digest(seed)
    document['conflicts'].sort(key=lambda row:row['conflict_id'])
    document['conflicts_sha256']=digest(document['conflicts'])
    return jcs(document)


@pytest.mark.parametrize('edit',['drop','add','value','impact','source','history','observation'])
def test_native_reader_rejects_rehashed_forgery_not_just_broken_hashes(bound,edit):
    sources,history,plan=bound
    value=plan.data;row=value['conflicts'][0]
    if edit=='drop': value['conflicts'].clear()
    elif edit=='add':
        other=deepcopy(row);other['pointer']='/another';value['conflicts'].append(other)
    elif edit=='value': row['values']['ours']['value']='forged'
    elif edit=='impact':
        row['impact']['by_role']['ours']=[{'relation_id':'REL-forged','source_id':row['artifact_ids'][0],
            'target_id':'SR-REQ-forged','relation_type':'conflicts_with'}]
    elif edit=='source': value['source_bindings']['ours']['model_root_sha256']='a'*64
    elif edit=='history': value['history_input_sha256']='b'*64
    else: row['observations']['ours']['byte_sha256']='c'*64
    raw=rehash(value)
    # Structural inspection is explicitly not a revalidation of original inputs.
    assert parse_merge_conflicts(raw).data==value
    with pytest.raises(ModelError) as error: read_merge_conflicts(raw,sources,history=history)
    assert error.value.reason=='merge_conflicts_binding_mismatch'


@pytest.mark.parametrize('edit',['version','extra','row_extra','duplicate','id','hash','ready','allow',
    'missing_value','mixed_value','binary_domain','element','owner','artifact','pointer','impact_duplicate'])
def test_closed_reader_rejects_malformed_or_contradictory_rows(bound,edit):
    _,_,plan=bound;value=plan.data;row=value['conflicts'][0]
    if edit=='version': value['conflict_format_version']='merge-conflicts-v2'
    elif edit=='extra': value['extra']=1
    elif edit=='row_extra': row['extra']=1
    elif edit=='duplicate': value['conflicts'].append(deepcopy(row))
    elif edit=='id': row['conflict_id']='MC-'+'f'*64
    elif edit=='hash': value['source_bindings_sha256']='f'*64
    elif edit=='ready': value['ready']=True
    elif edit=='allow': row['allowed_resolutions'].append('force')
    elif edit=='missing_value': del row['values']['base']
    elif edit=='mixed_value': row['values']['ours']={'state':'absent','value':None}
    elif edit=='binary_domain': row['values']['ours']={'state':'present','domain':'bytes-v1','size':0,'sha256':sha256(b'').hexdigest()}
    elif edit=='element': row['element_keys']=['unrelated']
    elif edit=='owner': row['observations']['ours']['owner_id']='foreign-owner'
    elif edit=='artifact': row['artifact_ids']=[]
    elif edit=='pointer': row['pointer']='/bad~2escape'
    else:
        edge={'relation_id':'REL-duplicate','source_id':row['artifact_ids'][0],'target_id':'target','relation_type':'refines'}
        row['impact']['by_role']['ours']=[edge,edge]
    value['conflicts_sha256']=digest(value['conflicts'])
    with pytest.raises(ModelError): parse_merge_conflicts(jcs(value))


def test_escaped_keys_and_many_branches_are_retained_without_a_display_limit(tmp_path,original):
    path,value=artifact(original)
    variants=[changed(value,extensions={'vendor.conflict':{f'a/{i}~b':role for i in range(20)}}) for role in ROLES]
    sources,history=bound_records(tmp_path,original,path,variants)
    rows=catalogue(sources,history).conflicts
    assert len(rows)==20 and len({row['conflict_id'] for row in rows})==20
    assert {row['pointer'] for row in rows}=={f'/extensions/vendor.conflict/a~1{i}~0b' for i in range(20)}


def test_collection_conflict_keeps_whole_values_and_stable_keys(tmp_path,original):
    from specroad.model.paths import artifact_path
    value=record_value('configuration');path=artifact_path('configuration',value['id'],'SR')
    variants=[value,deepcopy(value),deepcopy(value)]
    # Every native source must remain valid when its dimension is removed.
    variants[1]['dimensions']=[]
    variants[1]['selection']={}
    variants[2]['dimensions'][0]['default']='windows'
    sources,history=bound_records(tmp_path,original,path,variants)
    row,=catalogue(sources,history).conflicts
    assert row['pointer']=='/dimensions' and row['element_keys']==['platform']
    assert row['conflict_class']=='set_element_conflict'
    for role,v in zip(ROLES,variants): assert row['values'][role]['value']==v['dimensions']


def test_binary_originals_keep_hash_size_and_never_offer_json_value(tmp_path,original):
    path=next(path for path in original if path.startswith('attachments/'))
    versions=[]
    for raw in (b'base',b'',b'other'):
        files=dict(original);files[path]=raw
        # Native manifests/descriptors must match actual bytes, never forged hashes.
        for name,data in list(files.items()):
            if not name.startswith('spec/'): continue
            value=json.loads(data)
            def update(item):
                if type(item) is dict:
                    if item.get('path')==path and 'sha256' in item:
                        item['sha256']=sha256(raw).hexdigest()
                        if 'size' in item:item['size']=len(raw)
                    for child in item.values(): update(child)
                elif type(item) is list:
                    for child in item: update(child)
            update(value);files[name]=jcs(value)
        versions.append(files)
    sources=bind_files(tmp_path,versions);plan=catalogue(sources,history_for(sources))
    row=next(row for row in plan.conflicts if row['identity']['kind']=='attachment')
    assert row['values']['ours']=={'state':'present','domain':'bytes-v1','size':0,'sha256':sha256(b'').hexdigest()}
    assert row['allowed_resolutions']==['take_ours','take_theirs','take_base']
    assert row['artifact_ids']==[] and all(not items for items in row['impact']['by_role'].values())


def test_base_resource_absence_is_not_a_null_or_delete_choice(tmp_path,original):
    path,value=artifact(original,'goal')
    sources,history=bound_records(tmp_path,original,path,[value,None,value])
    row=next(row for row in catalogue(sources,history).conflicts if row['identity']['id']==value['id'])
    assert row['conflict_class']=='artifact_absence_unproven'
    assert row['values']['ours']=={'state':'absent'}
    assert row['observations']['ours']['state']=='absent' and row['allowed_resolutions']==[]


def test_relation_positions_do_not_turn_into_common_field_pointers(tmp_path,original):
    a=edge(number=1);values=[edge(number=2,rationale=role) for role in ROLES]
    sources,history,owner=bound_relations(tmp_path,original,[[a,values[0]],[values[1],a],[a,values[2]]])
    row,=catalogue(sources,history).conflicts
    assert row['pointer']=='/relation/rationale'
    assert [row['observations'][role]['pointer'] for role in ROLES]==['/relations/1','/relations/0','/relations/1']
    assert row['artifact_ids']==[owner]


def test_audit_metadata_is_pending_k3_not_ordinary_conflict(tmp_path,original):
    path,value=artifact(original)
    versions=[changed(value,revision=i,updated_at=f'2026-11-0{i}T00:00:00Z') for i in (1,2,3)]
    sources,history=bound_records(tmp_path,original,path,versions)
    result=catalogue(sources,history)
    assert result.conflicts==[] and 'merge_metadata' in result.data['pending_gates']


def test_currentness_is_checked_before_native_reader_returns(bound):
    sources,history,plan=bound
    with patch.object(SourceSnapshot,'verify_current',side_effect=ModelError('changed_source')):
        with pytest.raises(ModelError) as error: read_merge_conflicts(plan.canonical_bytes,sources,history=history)
    assert error.value.reason=='changed_source'


@pytest.mark.parametrize('raw',[b'{}',b'[]',b'{"x":1,"x":2}',b'not json',b'\xff'])
def test_cli_reports_invalid_plan_as_model_error_without_write(tmp_path,raw):
    file=tmp_path/'bad.json';file.write_bytes(raw);before=inventory(tmp_path)
    assert dispatch_result(['merge','conflicts',str(file),'--format','json']).exit_code==3
    assert inventory(tmp_path)==before


def test_cli_does_not_open_any_source_or_history_provider(bound,tmp_path):
    _,_,plan=bound;file=tmp_path/'merge.json';file.write_bytes(plan.canonical_bytes)
    with patch.object(SourceSnapshot,'verify_current',side_effect=AssertionError('stored display must not open sources')):
        result=dispatch_result(['merge','conflicts',str(file),'--format','json'])
    assert result.exit_code==0
    assert thaw(result.result)['source_validation']=='not_revalidated'


@pytest.mark.parametrize('kind',['leaf_link','parent_link','directory','missing','fifo'])
def test_cli_rejects_linked_special_or_missing_inputs(bound,tmp_path,kind):
    _,_,plan=bound;file=tmp_path/'merge.json';file.write_bytes(plan.canonical_bytes)
    target=tmp_path/'bad'
    if kind=='leaf_link':target.symlink_to(file)
    elif kind=='parent_link':
        target.symlink_to(tmp_path,target_is_directory=True);target=target/'merge.json'
    elif kind=='directory':target.mkdir()
    elif kind=='fifo':
        import os
        if not hasattr(os,'mkfifo'):pytest.skip('FIFO not supported by host')
        os.mkfifo(target)
    result=dispatch_result(['merge','conflicts',str(target),'--format','json'])
    assert result.exit_code==(5 if kind=='missing' else 7)


def test_cli_rejects_plan_changed_between_reads(bound,tmp_path):
    _,_,plan=bound;file=tmp_path/'merge.json';file.write_bytes(plan.canonical_bytes)
    with patch.object(ProjectBoundary,'read_bytes',side_effect=[plan.canonical_bytes,b'changed']):
        result=dispatch_result(['merge','conflicts',str(file),'--format','json'])
    assert result.exit_code==7


def test_guard_does_not_hide_independent_field_conflicts(tmp_path,original):
    path,value=artifact(original)
    variants=[changed(value,maturity=state,title=role) for state,role in zip(('draft','proposed','rejected'),ROLES)]
    sources,history=bound_records(tmp_path,original,path,variants)
    rows=catalogue(sources,history).conflicts
    assert {(row['conflict_class'],row['pointer']) for row in rows}=={
        ('lifecycle_transition_conflict',''),('scalar_change','/title')}
    assert all(row['allowed_resolutions']==[] for row in rows)
    field=next(row for row in rows if row['pointer']=='/title')
    assert {role:field['values'][role]['value'] for role in ROLES}==dict(zip(ROLES,ROLES))


def test_history_input_is_owned_before_native_source_work(bound):
    from specroad.merge import conflicts as service
    sources,history,expected=bound
    original_sources=service._sources
    def concurrent_caller_edit(current):
        result=original_sources(current)
        history['observations'].clear()
        return result
    with patch.object(service,'_sources',side_effect=concurrent_caller_edit):
        actual=catalogue(sources,history)
    assert actual.canonical_bytes==expected.canonical_bytes
    assert history['observations']==[]
