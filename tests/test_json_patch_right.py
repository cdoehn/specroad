"""Error atomicity, raw inputs, preconditions and an independent array oracle."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, localcontext
import builtins
import json
import math
import random
import socket
import subprocess
from unittest.mock import patch
import pytest
from specroad.changes import (JsonPatch, JsonPatchError, ChangeOperation, ChangePlanError,
    apply_json_patch, compile_field_patch, preview_update, preview_update_bytes, preview_field_update)
from specroad.model.canonical import canonical_json_sha256
from support.domain import domain_value
from support.change_plans import operation
from support.portable import build_distribution
from support.processes import run_python


def test_raw_patch_rejects_duplicate_members_without_source_mutation():
    raw=b'[{"op":"remove","op":"add","path":"/x","value":1}]'
    with pytest.raises(JsonPatchError) as err: JsonPatch.from_bytes(raw)
    assert err.value.reason=='duplicate_key'
    assert raw==b'[{"op":"remove","op":"add","path":"/x","value":1}]'


def test_raw_patch_keeps_original_bytes_and_passive_members():
    raw=b' [ { "op":"add", "path":"/x", "value": 1, "comment": "keep" } ] \n'
    p=JsonPatch.from_bytes(raw)
    assert p.source_bytes==raw and p.apply({}).data=={'x':1}
    assert p.data[0]['comment']=='keep'
    p.data[0]['value']=99
    assert p.apply({}).data=={'x':1}


@pytest.mark.parametrize('raw',[b'[] true',b'[],"other":{}', b'[],"value":[]', b'[]}',b'\xef\xbb\xbf[]',
    b'\xff',b'{}',b'null',b'[{"op":"add","path":"/x","value":NaN}]',b'[{"op":"add","path":"/x","value":"\\ud800"}]'])
def test_raw_patch_accepts_exactly_one_strict_array(raw):
    with pytest.raises(JsonPatchError): JsonPatch.from_bytes(raw)


def test_strict_raw_inputs_never_silently_round_numbers():
    for token in ['9007199254740993','0.100000000000000001','1e-999','1e999']:
        with pytest.raises(JsonPatchError): JsonPatch.from_bytes(('[{"op":"add","path":"/x","value":'+token+'}]').encode())
        with pytest.raises(JsonPatchError): compile_field_patch({},[('--set','/x='+token)])
    assert compile_field_patch({},[('--set','/x=0.1')]).apply({}).data=={'x':0.1}


@pytest.mark.parametrize('value',[False,True,0,-1,1.5,'1',None])
def test_invalid_expected_revision_is_not_coerced(value):
    with pytest.raises(ChangePlanError): preview_field_update(domain_value(),[],expected_revision=value)


@pytest.mark.parametrize('value',[None,'','A'*64,'0'*63,True,1])
def test_invalid_hash_is_not_an_absent_guard(value):
    with pytest.raises(ChangePlanError): preview_field_update(domain_value(),[],expected_revision=1,expected_sha256=value)


def test_comfort_update_binds_actual_base_and_retains_source_bytes():
    base=domain_value();opts=[('--set','/statement="Changed."')]
    result=preview_field_update(base,opts,expected_sha256=canonical_json_sha256(base))
    op=result.operation.data
    assert 'expected_revision' not in op and op['expected_sha256']==canonical_json_sha256(base)
    raw_base=json.dumps(base,ensure_ascii=True,indent=3).encode();raw_op=json.dumps(op,indent=2).encode()
    byte_result=preview_update_bytes(raw_base,raw_op)
    assert byte_result.candidate==result.candidate
    assert byte_result.source_bytes==raw_base and byte_result.operation_bytes==raw_op
    assert byte_result.base_sha256==canonical_json_sha256(base)
    assert byte_result.candidate['revision']==1 and not byte_result.metadata_applied


def test_base_preconditions_fail_before_comfort_execution():
    with pytest.raises(ChangePlanError) as error:
        preview_field_update(domain_value(),[('--set','/missing/child=invalid')],expected_revision=2)
    assert error.value.reason=='expected_revision_mismatch'


def test_controlled_parent_writes_cannot_be_hidden_by_later_restore():
    base=domain_value()
    for name in ['id','revision','maturity','created_by','relations']:
        op=operation('update');op['patch']=[{'op':'add','path':'/'+name,'value':None},
            {'op':'add','path':'/'+name,'value':base.get(name)}]
        with pytest.raises(ChangePlanError): preview_update(base,op)
    with pytest.raises(ChangePlanError): preview_field_update(base,[('--unset','/revision'),('--set','/revision=1')],expected_revision=1)
    assert base==domain_value()


def test_whole_artifact_root_writes_are_rejected_even_if_final_identity_unchanged():
    base=domain_value();op=operation('update')
    for kind in ['add','replace','remove','move','copy']:
        item={'op':kind,'path':'','value':base,'from':'/statement'}
        op['patch']=[item]
        with pytest.raises(ChangePlanError): preview_update(base,op)


def test_controlled_fields_can_be_read_but_not_consumed():
    base=domain_value();op=operation('update')
    op['patch']=[{'op':'test','path':'/revision','value':1},{'op':'copy','from':'/id','path':'/title'}]
    r=preview_update(base,op)
    assert r.candidate['id']==base['id'] and r.candidate['title']==base['id']


def test_nested_ordinary_fields_named_like_controlled_fields_remain_editable():
    base=domain_value(extensions={'acme.test':{'id':'old','revision':1}})
    result=preview_field_update(base,[('--set','/extensions/acme.test/id="new"')],expected_revision=1)
    assert result.candidate['extensions']['acme.test']=={'id':'new','revision':1}
    assert result.candidate['id']==base['id']


def test_no_live_revision_is_invented_for_comfort_input():
    with pytest.raises(ChangePlanError): preview_field_update(domain_value(),[('--set','/statement="x"')])


def test_no_serialization_changes_the_original_or_a_later_preview():
    base=domain_value();r=preview_field_update(base,[('--set','/statement="Changed"')],expected_revision=1)
    r.candidate['created_by']['actor_id']='mutated'
    assert r.candidate['created_by']==base['created_by']
    assert r.operation.data['target']==base['id']
    assert preview_field_update(base,[],expected_revision=1).candidate==base


def test_move_array_indices_match_independent_list_oracle():
    for length in range(1,16):
        for source in range(length):
            for target in range(length):
                original=list(range(length));expected=original.copy();moved=expected.pop(source);expected.insert(target,moved)
                actual=apply_json_patch(original,[{'op':'move','from':'/'+str(source),'path':'/'+str(target)}]).data
                assert actual==expected and original==list(range(length))


def test_array_splicing_matches_independent_integer_sequence_operations():
    rng=random.Random(902)
    for _ in range(100):
        original=list(range(rng.randrange(8)));expected=original.copy();ops=[]
        for i in range(25):
            kind=rng.choice(['add','remove','replace','copy']) if expected else 'add'
            if kind=='add':
                index=rng.randrange(len(expected)+1);value=rng.randrange(100)
                expected.insert(index,value);ops.append({'op':kind,'path':'/'+str(index),'value':value})
            elif kind=='remove':
                index=rng.randrange(len(expected));expected.pop(index);ops.append({'op':kind,'path':'/'+str(index)})
            elif kind=='replace':
                index=rng.randrange(len(expected));value=rng.randrange(100)
                expected[index]=value;ops.append({'op':kind,'path':'/'+str(index),'value':value})
            else:
                source=rng.randrange(len(expected));target=rng.randrange(len(expected)+1)
                expected.insert(target,expected[source]);ops.append({'op':kind,'from':'/'+str(source),'path':'/'+str(target)})
        assert apply_json_patch(original,ops).data==expected


def test_move_failed_destination_does_not_lose_source_in_caller():
    original={'a':[1,2], 'b':None}
    with pytest.raises(JsonPatchError): apply_json_patch(original,[{'op':'move','from':'/a','path':'/missing/x'}])
    assert original=={'a':[1,2], 'b':None}


def test_copy_to_own_descendant_is_finite_detached_and_allowed():
    original={'a':{'x':1}}
    assert apply_json_patch(original,[{'op':'copy','from':'/a','path':'/a/child'}]).data=={'a':{'x':1,'child':{'x':1}}}
    assert original=={'a':{'x':1}}


def test_root_move_copy_and_restoration_preserve_null_distinction():
    assert apply_json_patch({'a':None},[{'op':'move','from':'/a','path':''}]).data is None
    assert apply_json_patch({'a':1},[{'op':'copy','from':'','path':'/b'}]).data=={'a':1,'b':{'a':1}}
    p=compile_field_patch({'x':1},[('--unset',''),('--set','=null')])
    assert p.apply({'x':1}).data is None
    assert p.data[-1]['op']=='add'


@pytest.mark.parametrize('kind',['test','replace','remove','copy','move'])
def test_operations_after_removed_root_cannot_read_a_fake_null(kind):
    op={'op':kind,'path':'','value':None,'from':''}
    with pytest.raises(JsonPatchError) as err: apply_json_patch(None,[{'op':'remove','path':''},op])
    assert err.value.reason=='document_absent' and err.value.operation_index==1


def test_pointer_escaping_is_decoded_once_not_normalized():
    original={'~1':1,'/':2,'a':{'b':3},'a/b':4,'a%2Fb':5,'a.b':6,'e\u0301':7,'é':8}
    for ptr,value in [('/~01',1),('/~1',2),('/a/b',3),('/a~1b',4),('/a%2Fb',5),('/a.b',6),('/e\u0301',7),('/é',8)]:
        assert apply_json_patch(original,[{'op':'test','path':ptr,'value':value}]).document_exists


@pytest.mark.parametrize('index',['/a/3','/a/01','/a/-/x','/a/١'])
def test_set_cannot_make_holes_or_treat_invalid_indices_as_new_keys(index):
    original={'a':[1,2]}
    with pytest.raises(JsonPatchError): compile_field_patch(original,[('--set',index+'=0')])
    assert original=={'a':[1,2]}


def test_large_valid_operation_list_has_no_display_limit():
    operations=[{'op':'add','path':'/-','value':i} for i in range(1501)]
    r=apply_json_patch([],operations)
    assert r.data==list(range(1501)) and r.operations_applied==1501


def test_deep_values_do_not_require_python_recursion():
    original=7
    for _ in range(1300): original={'x':original}
    pointer='/x'*1300
    out=apply_json_patch(original,[{'op':'test','path':pointer,'value':7},{'op':'replace','path':pointer,'value':8}]).data
    for _ in range(1300): original=original['x'];out=out['x']
    assert original==7 and out==8


def test_deep_copy_and_equality_do_not_recurse_or_alias():
    deep=[]
    for _ in range(1200): deep=[deep]
    original={'a':deep}
    out=apply_json_patch(original,[{'op':'copy','from':'/a','path':'/b'}, {'op':'test','path':'/b','value':deep}]).data
    x,y=out['a'],out['b']
    for _ in range(1200):
        assert x is not y;x=x[0];y=y[0]
    assert x==y==[] and x is not y


@pytest.mark.parametrize('value',[float('inf'),float('nan'),Decimal('1'),b'text',{1:'x'}])
def test_nonjson_input_is_not_coerced(value):
    with pytest.raises(JsonPatchError): apply_json_patch(value,[])


def test_cyclic_values_are_refused_and_shared_values_are_copied():
    cycle=[];cycle.append(cycle)
    with pytest.raises(JsonPatchError): apply_json_patch(cycle,[])
    assert cycle[0] is cycle
    shared=[];original={'a':shared,'b':shared}
    result=apply_json_patch(original,[{'op':'add','path':'/a/-','value':1}]).data
    assert result=={'a':[1],'b':[]} and shared==[]


def test_foreign_object_hooks_are_not_called():
    class Foreign(dict):
        def __iter__(self): raise AssertionError('hook')
        def items(self): raise AssertionError('hook')
        def __deepcopy__(self,memo): raise AssertionError('hook')
        def __str__(self): raise AssertionError('hook')
    for action in [lambda:apply_json_patch(Foreign(),[]),lambda:JsonPatch([Foreign(op='add',path='/x',value=1)]),
                   lambda:compile_field_patch({},[('--set',Foreign())])]:
        with pytest.raises(JsonPatchError): action()


def test_pure_patch_has_no_file_network_or_process_effects(tmp_path):
    original={'secret':'${HOME} /etc/passwd'};program=JsonPatch([{'op':'copy','from':'/secret','path':'/new'}])
    with patch.object(builtins,'open',side_effect=AssertionError('open')),\
         patch.object(socket,'socket',side_effect=AssertionError('socket')),\
         patch.object(subprocess,'run',side_effect=AssertionError('process')):
        assert program.apply(original).data=={'secret':original['secret'],'new':original['secret']}
    assert list(tmp_path.iterdir())==[]


def test_diagnostic_does_not_contain_operand_values():
    secret='TOP-SECRET-OPERAND'
    with pytest.raises(JsonPatchError) as err:
        apply_json_patch({'x':secret},[{'op':'test','path':'/x','value':'different-secret'}])
    detail=json.dumps(err.value.diagnostic())
    assert secret not in detail and 'different-secret' not in detail
    assert err.value.diagnostic()['operation_index']==0


def test_repeated_and_concurrent_application_do_not_share_working_state():
    program=JsonPatch([{'op':'add','path':'/-','value':{'x':1}}])
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:program.apply([]).data,range(30)))
    results[0][0]['x']=99
    assert all(v==[{'x':1}] for v in results[1:])
    assert program.data[0]['value']=={'x':1}


def test_decimal_process_context_does_not_change_json_patch_semantics():
    with localcontext() as ctx:
        ctx.prec=1
        assert JsonPatch.from_bytes(b'[{"op":"add","path":"/x","value":0.125}]').apply({}).data=={'x':.125}


def test_module_and_zipapp_include_patch_engine_and_preview(tmp_path):
    module,archive=build_distribution(tmp_path/'delivery')
    body="import sys;sys.path.insert(0,sys.argv[1]);from specroad.changes import JsonPatch,preview_update; p=JsonPatch.from_bytes(b'[{\\\"op\\\":\\\"add\\\",\\\"path\\\":\\\"/x\\\",\\\"value\\\":1}]');assert p.apply({}).data=={'x':1};from specroad.changes import preview_field_update; a=%r; r=preview_field_update(a,[('--set','/statement=\\\"new\\\"')],expected_revision=1);assert r.candidate['statement']=='new' and r.candidate['revision']==1 and not r.write_authorized" % domain_value()
    for location in [module,archive]:
        process=run_python(['-I','-S','-B','-c',body,str(location)],tmp_path,capture=True)
        assert process.returncode==0,process.stderr
