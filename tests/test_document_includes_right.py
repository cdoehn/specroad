"""Whole supplied graph boundaries and exact, nonduplicated include identities."""
from copy import deepcopy
from hashlib import sha256
import builtins
import io
import json
import os

import pytest

from specroad.changes import TargetModel
from specroad.documents import DocumentIncludeCycleError, compose_document
from specroad.model.errors import ModelError
from specroad.validation import ModelDocument
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import block_value, record_value, ref
from support.targets import model
from test_document_includes import edge, include_project, occurrence_ids


def ident(prefix, number): return f'SR-{prefix}-{number:026d}'


def document_mesh(adjacency):
    values = []; relation_number = 0; block_number = 0
    for number in sorted(adjacency):
        values.append(record_value('document', id=ident('DOC', number),
            document_role='primary_specification' if number == 0 else 'supporting',
            relations=[edge('contains', ident('SEC', number), relation_number)]))
        relation_number += 1; children = []; blocks = []
        for position, target in enumerate(adjacency[number] or [None]):
            block = block_value('include_document' if target is not None else 'prose')
            block['id'] = ident('BLOCK', block_number); block_number += 1
            children.append(edge('contains', block['id'], relation_number, position)); relation_number += 1
            if target is not None:
                block['relations'] = [edge('references', ident('DOC', target), relation_number)]
                relation_number += 1
            blocks.append(block)
        values.append(record_value('section', id=ident('SEC', number), relations=children)); values.extend(blocks)
    return values


def cycle_issue(values, selected=None):
    supplied = model(values); before = supplied.source_files
    with no_write_attempts(), pytest.raises(DocumentIncludeCycleError) as caught:
        compose_document(supplied, selected or ident('DOC', 0))
    assert supplied.source_files == before
    return supplied, caught.value


@pytest.mark.parametrize('selected', [0, 1, 2])
def test_three_document_cycle_reports_the_same_actual_cycle_independently_of_selected_root(selected):
    values = document_mesh({0:[1],1:[2],2:[0]}); supplied, error = cycle_issue(values, ident('DOC', selected))
    issue = error.diagnostic()
    assert len(issue['edges']) == 9 and len(issue['artifact_ids']) == 10
    assert set(issue['artifact_ids']) == {ident(prefix, n) for prefix in ('DOC','SEC','BLOCK') for n in range(3)}
    assert issue == cycle_issue(list(reversed(values)), ident('DOC', 0))[1].diagnostic()
    for i, row in enumerate(issue['edges']):
        assert (row['source_id'],row['target_id']) == tuple(issue['artifact_ids'][i:i+2])
        raw = supplied.source_files[row['path']]; source = json.loads(raw)
        assert row['relation'] == source['relations'][int(row['pointer'].split('/')[-1])]
        assert row['source_sha256'] == sha256(raw).hexdigest()


def test_unreachable_cycle_still_blocks_an_empty_selected_document():
    values = document_mesh({0:[1],1:[0]})
    values.append(record_value('document', id=ident('DOC', 2), document_role='supporting'))
    _, error = cycle_issue(values, ident('DOC', 2))
    assert ident('DOC', 2) not in error.diagnostic()['artifact_ids']


def test_mixed_content_and_section_include_cycle_is_detected_on_the_actual_occurrence_graph():
    values = include_project(); values[-1]['block_kind'] = 'include_document'
    values[-1]['payload'] = {'mode':'section'}; values[-1]['relations'] = [edge('references',ref('SEC'),7)]
    _, error = cycle_issue(values, ref('DOC')); issue = error.diagnostic()
    assert len(issue['edges']) == 5
    assert {r['include_mode'] for r in issue['edges'] if r['kind']=='include'} == {'content','section'}
    assert ref('DOC') not in issue['artifact_ids']


@pytest.mark.parametrize('selected', [0,1])
def test_cross_document_section_reuse_is_valid_when_no_actual_include_path_returns(selected):
    # Each document includes the other document's leaf section. Coarsening these
    # real edges to document-to-document dependencies would invent a cycle.
    values = document_mesh({0:[],1:[]})
    for number in range(2):
        doc = next(v for v in values if v['id']==ident('DOC',number))
        new_section=ident('SEC',number+2); new_block=ident('BLOCK',number+2)
        doc['relations'].append(edge('contains',new_section,20+number,1))
        values.append(record_value('section',id=new_section,relations=[edge('contains',new_block,22+number)]))
        block=block_value('include_document');block['id']=new_block;block['payload']={'mode':'section'}
        block['relations']=[edge('references',ident('SEC',1-number),24+number)];values.append(block)
    with no_write_attempts(): result=compose_document(model(values),ident('DOC',selected))
    assert occurrence_ids(result)==[ident('DOC',selected),ident('SEC',selected),ident('BLOCK',selected),
        ident('SEC',selected+2),ident('BLOCK',selected+2),ident('SEC',1-selected),ident('BLOCK',1-selected)]
    assert len(result.data['include_edges'])==2


def test_diamond_include_paths_keep_both_terminal_occurrences_with_one_original_record():
    values=document_mesh({0:[1,2],1:[3],2:[3],3:[]})
    with no_write_attempts(): result=compose_document(model(values),ident('DOC',0))
    rows=result.data['occurrences'];leaf=ident('BLOCK',4)
    assert len(rows)==16 and len(result.data['records'])==13
    repeated=[r for r in rows if r['artifact_id']==leaf]
    assert len(repeated)==2 and repeated[0]['parent_occurrence']!=repeated[1]['parent_occurrence']
    assert result.data['records'][leaf]['record']==next(v for v in values if v['id']==leaf)


def test_repeated_contains_edges_keep_their_own_relation_provenance_and_full_include_content():
    values=include_project(); values[2]['relations'].append(edge('contains',ref('BLOCK'),8,2))
    result=compose_document(model(values),ref('DOC'));rows=result.data['occurrences']
    repeats=[r for r in rows if r['artifact_id']==ref('BLOCK')]
    assert [r['via']['relation_id'] for r in repeats]==['REL-'+f'{n:026d}' for n in (2,8)]
    assert occurrence_ids(result).count(ref('BLOCK','2'))==3
    assert len(result.data['records'])==7


def test_wide_acyclic_reuse_keeps_all_paths_without_a_hidden_visit_or_count_cap():
    count=64;values=document_mesh({0:[1]*count,1:[]})
    result=compose_document(model(values),ident('DOC',0))
    assert result.data['occurrence_count']==2+count*4
    assert len(result.data['records'])==count+5
    assert occurrence_ids(result).count(ident('BLOCK',count))==count


def test_unplaced_include_is_checked_but_does_not_invent_a_document_occurrence():
    values=include_project(); block=block_value('include_document');block['id']=ref('BLOCK','3')
    block['relations']=[edge('references',ref('DOC'),7)];values.append(block)
    result=compose_document(model(values),ref('DOC'))
    assert len(result.data['include_edges'])==3
    assert ref('BLOCK','3') not in occurrence_ids(result) and ref('BLOCK','3') not in result.data['records']


@pytest.mark.parametrize('extra',['target_id','document_id','template','script','source_url','loader','record'])
def test_include_payload_cannot_supply_a_copied_target_or_executable_external_provider(extra):
    values=include_project();values[4]['payload'][extra]=deepcopy(values[1]) if extra=='record' else 'external.call()'
    with no_write_attempts(),pytest.raises(ModelError):compose_document(model(values),ref('DOC'))


@pytest.mark.parametrize('failure',['second_reference','other_relation_type','duplicate_relation_id','title_alias'])
def test_exact_native_reference_contract_cannot_be_bypassed_by_an_alternative_edge(failure):
    values=include_project()
    if failure=='second_reference':values[4]['relations'].append(edge('references',ref('DOC','1'),9))
    elif failure=='other_relation_type':values[4]['relations'][0]['type']='derived_from'
    elif failure=='duplicate_relation_id':values[5]['relations'][0]['relation_id']=values[4]['relations'][0]['relation_id']
    else:values[1]['id']=ref('DOC','2')
    with no_write_attempts(),pytest.raises(ModelError):compose_document(model(values),ref('DOC'))


def test_cycle_diagnostic_is_detached_and_reordered_arrays_keep_actual_source_pointers():
    values = document_mesh({0:[1,1],1:[0]}); _, first = cycle_issue(values)
    old = first.diagnostic(); changed = first.diagnostic(); changed['edges'].clear(); changed['artifact_ids'].clear()
    assert first.diagnostic() == old
    for value in values: value['relations'].reverse()
    supplied, second = cycle_issue(values); after = second.diagnostic()
    assert after['artifact_ids'] == old['artifact_ids'] and after['relation_ids'] == old['relation_ids']
    for row in after['edges']:
        raw = supplied.source_files[row['path']]
        assert row['relation'] == json.loads(raw)['relations'][int(row['pointer'].split('/')[-1])]
        assert row['source_sha256'] == sha256(raw).hexdigest()
    assert after['edges'] != old['edges']


@pytest.mark.parametrize('kind', ['document','section','content_block'])
def test_byte_only_source_change_rebinds_without_inventing_new_revisions_or_model_content(kind):
    supplied = model(include_project()); first = compose_document(supplied, ref('DOC'))
    source = next(d for d in supplied.documents if json.loads(d.content)['artifact_type'] == kind)
    value = json.loads(source.content); raw = (json.dumps(value, indent=4) + '\n').encode()
    changed = TargetModel(supplied.configuration_bytes, supplied.binding,
        [ModelDocument(d.path, raw if d.path == source.path else d.content) for d in supplied.documents],
        profile=supplied.profile, resource_files=supplied.resource_files)
    with no_write_attempts(): second = compose_document(changed, ref('DOC'))
    a,b = first.data,second.data
    assert a['model_root_sha256'] == b['model_root_sha256'] and a['input_sha256'] != b['input_sha256']
    assert a['structure_sha256'] != b['structure_sha256']
    before,after = a['records'][value['id']],b['records'][value['id']]
    assert before['record'] == after['record'] and before['revision'] == after['revision']
    assert before['record_sha256'] == after['record_sha256']
    assert before['source_sha256'] != after['source_sha256'] == sha256(raw).hexdigest()
    assert second.source_files[source.path] == raw and first.source_files[source.path] == source.content
    assert occurrence_ids(first) == occurrence_ids(second)


def test_duplicate_document_identity_cannot_select_a_more_convenient_target_copy():
    supplied = model(include_project()); source = next(d for d in supplied.documents
        if json.loads(d.content)['id'] == ref('DOC','1'))
    value = json.loads(source.content); value['relations'] = []; value['revision'] = 2
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        TargetModel(supplied.configuration_bytes, supplied.binding,
            [*supplied.documents,ModelDocument('artifacts/document/copy.json',json.dumps(value).encode())],
            profile=supplied.profile, resource_files=supplied.resource_files)
    assert caught.value.reason == 'target_duplicate_artifact_id'


def test_tampered_owned_sources_cannot_reuse_the_previous_acyclic_model_binding():
    supplied = model(include_project()); docs = list(supplied.documents)
    docs[0] = ModelDocument(docs[0].path, docs[0].content + b'\n'); object.__setattr__(supplied,'documents',tuple(docs))
    with no_write_attempts(), pytest.raises(ModelError) as caught: compose_document(supplied,ref('DOC'))
    assert caught.value.reason == 'target_sources_changed'


@pytest.mark.parametrize('cyclic',[False,True])
def test_include_admission_and_composition_do_not_read_source_paths_or_run_external_code(tmp_path,monkeypatch,cyclic):
    supplied = model(document_mesh({0:[1],1:[0] if cyclic else []}))
    for name,raw in supplied.source_files.items():
        p = tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    before = inventory(tmp_path);calls=[]
    def forbidden(*args,**kwargs):
        calls.append((args,kwargs));raise AssertionError('Unexpected source read')
    with no_write_attempts(),monkeypatch.context() as guard:
        for owner in (builtins,io,os):guard.setattr(owner,'open',forbidden)
        if cyclic:
            with pytest.raises(DocumentIncludeCycleError):compose_document(supplied,ident('DOC',0))
        else:
            result=compose_document(supplied,ident('DOC',0));assert result.data['occurrence_count']==6
    assert calls==[] and inventory(tmp_path)==before


@pytest.mark.parametrize('mode',['core','pyz'])
def test_multidocument_cycle_has_the_same_bound_machine_diagnostic_in_core_and_pyz(tmp_path,mode):
    supplied, error = cycle_issue(document_mesh({0:[1],1:[2],2:[0]}));expected=error.diagnostic()
    body='''import json
from specroad.documents import compose_document,DocumentIncludeCycleError
from specroad.changes import TargetModel
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource,compose_profiles
from specroad.validation import ModelDocument
'''
    body+='config='+repr(supplied.configuration_bytes)+'\n'
    body+='documents='+repr([(d.path,d.content) for d in supplied.documents])+'\n'
    body+='resources='+repr([(d.path,d.content) for d in supplied.resource_files])+'\n'
    body+='core_key='+repr(supplied.profile.profile_chain[0])+'\n'
    body+='''profile=compose_profiles([ProfileResource(raw) for path,raw in resources],core_key=core_key)
owned=TargetModel(config,ProjectReadBinding('sample','/explicit/provider',(1,2)),
 [ModelDocument(path,raw) for path,raw in documents],profile=profile,
 resource_files=[ModelDocument(path,raw) for path,raw in resources])
try:
'''
    body+=' compose_document(owned,'+repr(ident('DOC',0))+')\n'
    body+='''except DocumentIncludeCycleError as error:
 print(json.dumps(error.diagnostic(),sort_keys=True))
else:
 raise AssertionError('Cycle was accepted')
'''
    if mode=='core':result=run_core(body,tmp_path,capture=True)
    else:
        _,package=build_distribution(tmp_path/'distribution')
        result=run_python(['-I','-S','-B','-c',
            'import sys;sys.path.insert(0,'+repr(str(package))+')\n'+body],tmp_path,capture=True)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)==expected
