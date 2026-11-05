"""17.g.W: every original branch, stable addresses and real read-only CLI."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.merge import build_merge_conflicts, parse_merge_conflicts, read_merge_conflicts
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.errors import ModelError
from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.results import thaw
from specroad.cli.result_schemas import validate_result_document
from support.merge_lifecycle import artifact, bound_records, changed
from support.merge_relations import bound_relations, edge, history_for
from support.read_only import inventory
from test_merge_inventory import bind_files
from test_merge_sources import read_only_sources
from test_project_bundle import project

PLAN_ID = 'MP-' + '0'*26
ROLES = ('base','ours','theirs')


@pytest.fixture(scope='module')
def original(tmp_path_factory):
    return project(tmp_path_factory.mktemp('conflict-seed')/'project').raw


def catalogue(sources, history, plan_id=PLAN_ID):
    return build_merge_conflicts(sources,plan_id=plan_id,history=history)


def test_every_conflicting_leaf_is_addressable_with_three_original_values(tmp_path, original):
    path, value = artifact(original)
    versions = [changed(value,title=role,extensions={'vendor.conflict':{'x':i,'y':role}}) for i,role in enumerate(ROLES)]
    sources, history = bound_records(tmp_path,original,path,versions)
    before = inventory(tmp_path)
    with read_only_sources():
        result = catalogue(sources,history)
        reread = read_merge_conflicts(result.canonical_bytes,sources,history=history)
    assert inventory(tmp_path)==before
    rows = {r['pointer']:r for r in result.conflicts}
    assert set(rows)=={'/title','/extensions/vendor.conflict/x','/extensions/vendor.conflict/y'}
    for pointer,row in rows.items():
        assert row['identity']=={'kind':'artifact','id':value['id'],'version':None}
        assert row['artifact_ids']==[value['id']]
        assert row['conflict_class']=='scalar_change'
        assert row['allowed_resolutions']==['take_ours','take_theirs','take_base','value']
        for role,original_value in zip(ROLES,versions):
            expected = original_value
            for member in pointer[1:].split('/'): expected = expected[member]
            assert row['values'][role]=={'state':'present','domain':'json-v1','value':expected}
            assert row['observations'][role]['byte_sha256']==sha256(jcs(original_value)).hexdigest()
        assert result.conflict(row['conflict_id'])==row
    assert reread.canonical_bytes==result.canonical_bytes
    assert result.data['source_bindings']==sources.binding
    assert not result.ready and not result.write_authorized
    assert result.data['approval_granted'] is False and len(result.data['pending_gates'])==4


def test_ids_are_repeatable_order_independent_and_bound_to_plan_source_and_history(tmp_path, original):
    path,value=artifact(original)
    sources,history=bound_records(tmp_path,original,path,[changed(value,title=x) for x in ROLES])
    first=catalogue(sources,history)
    history['observations'].reverse()
    assert catalogue(sources,history).canonical_bytes==first.canonical_bytes
    row,=first.conflicts
    seed={name:first.data[name] for name in ('conflict_format_version','plan_id','source_bindings_sha256','history_input_sha256')}
    seed.update({name:row[name] for name in ('identity','pointer','conflict_class','element_keys')})
    assert row['conflict_id']=='MC-'+sha256(jcs(seed)).hexdigest()
    assert catalogue(sources,history,'MP-'+'0'*25+'1').conflicts[0]['conflict_id']!=row['conflict_id']
    for observation in history['observations']: observation['origin']['namespace']='another-known-fixture'
    assert catalogue(sources,history).conflicts[0]['conflict_id']!=row['conflict_id']


def test_missing_member_and_json_null_are_distinct_and_absence_is_not_take_delete(tmp_path, original):
    path,value=artifact(original)
    versions=[changed(value,extensions={'vendor.conflict':{'item':1}}),
              changed(value,extensions={'vendor.conflict':{}}),
              changed(value,extensions={'vendor.conflict':{'item':None}})]
    sources,history=bound_records(tmp_path,original,path,versions)
    row,=catalogue(sources,history).conflicts
    assert row['conflict_class']=='remove_edit'
    assert row['values']['ours']=={'state':'absent'}
    assert row['values']['theirs']=={'state':'present','domain':'json-v1','value':None}
    assert row['allowed_resolutions']==['take_theirs','take_base','value']


def test_relation_conflicts_keep_all_fields_and_exact_direct_impact(tmp_path, original):
    values=[edge(rationale=role,extensions={'vendor.conflict':{'x':i}}) for i,role in enumerate(ROLES)]
    second=edge(number=2)
    sources,history,owner=bound_relations(tmp_path,original,[[v,second] for v in values])
    rows=catalogue(sources,history).conflicts
    assert {r['pointer'] for r in rows}=={'/relation/rationale','/relation/extensions/vendor.conflict/x'}
    for row in rows:
        assert row['identity']['id']==values[0]['relation_id'] and row['artifact_ids']==[owner]
        assert row['impact']['scope']=='direct_source_relations'
        assert row['impact']['depth']==1 and row['impact']['transitive'] is False
        for role in ROLES:
            expected=[{'relation_id':v['relation_id'],'source_id':owner,'target_id':v['target'],'relation_type':v['type']}
                      for v in (values[0],second)]
            assert row['impact']['by_role'][role]==sorted(expected,key=jcs)


@pytest.mark.parametrize('mode',['origin','immutable','lifecycle'])
def test_protection_conflicts_offer_no_bypass(tmp_path,original,mode):
    path,value=artifact(original,'evidence' if mode=='immutable' else 'goal')
    if mode=='lifecycle':
        versions=[changed(value,maturity=s) for s in ('draft','proposed','rejected')]
    else: versions=[value,changed(value,title='different'),value]
    sources,history=bound_records(tmp_path,original,path,versions)
    if mode=='origin':
        next(row for row in history['observations'] if row['role']=='ours' and row['identity']['id']==value['id'])['origin']=None
    result=catalogue(sources,history)
    assert result.conflicts
    assert all(row['allowed_resolutions']==[] for row in result.conflicts)
    assert all(row['pointer']=='' for row in result.conflicts)


def test_independent_fields_and_schema_sets_do_not_become_artificial_conflicts(tmp_path,original):
    path,value=artifact(original)
    versions=[changed(value,tags=['base']),changed(value,tags=['base','ours'],title='ours'),
              changed(value,tags=['theirs','base'],extensions={'vendor.add':{'x':1}})]
    sources,history=bound_records(tmp_path,original,path,versions)
    result=catalogue(sources,history)
    assert result.conflicts==[] and not result.ready
    assert result.data['pending_gates']==['audited_resolution','merge_metadata','target_validation','publication']


def test_machine_cli_and_structured_request_inspect_same_passive_plan(tmp_path,original):
    path,value=artifact(original)
    (tmp_path/'sources').mkdir()
    sources,history=bound_records(tmp_path/'sources',original,path,[changed(value,title=r) for r in ROLES])
    plan=catalogue(sources,history)
    file=tmp_path/'merge.json';file.write_bytes(plan.canonical_bytes)
    before=inventory(tmp_path)
    response=dispatch_result(['merge','conflicts',str(file),'--format','json'])
    structured=execute_request({'command_id':'merge.conflicts','arguments':{'merge_plan':str(file)},'options':{'--format':'json'}}).result
    assert response.exit_code==0 and structured.exit_code==0
    payload=thaw(response.result)
    assert payload==thaw(structured.result)=={'format_version':'merge-conflicts-command-v1',
        'source_validation':'not_revalidated','plan_sha256':plan.sha256,'plan':plan.data}
    validate_result_document('merge-conflicts-command-v1',payload)
    assert inventory(tmp_path)==before


def test_returned_data_is_detached_and_never_truthy_approval(tmp_path,original):
    path,value=artifact(original)
    sources,history=bound_records(tmp_path,original,path,[changed(value,title=r) for r in ROLES])
    result=catalogue(sources,history);identifier=result.conflicts[0]['conflict_id']
    result.data['conflicts'].clear();result.conflict(identifier)['values'].clear()
    assert result.conflicts[0]['values']
    assert parse_merge_conflicts(result.canonical_bytes).sha256==result.sha256
    with pytest.raises(ModelError): result.conflict('unknown')
    with pytest.raises(FrozenInstanceError): result._encoded=b'{}'
    with pytest.raises(TypeError): bool(result)
