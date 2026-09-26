"""RFC-6902 value semantics and guarded update candidates, not CLI layout."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import pytest
from specroad.changes import (JsonPatch, JsonPatchError, ChangePlanError,
    apply_json_patch, compile_field_patch, preview_update)
from specroad.model.canonical import canonical_json_sha256
from support.domain import domain_value
from support.change_plans import operation
from support.records import record_value


def test_rfc6902_examples():
    vectors = json.loads((Path(__file__).parent / 'data/json-patch-rfc6902-v1.json').read_bytes())
    for case in vectors['cases']:
        original = deepcopy(case['document']); ops = deepcopy(case['patch'])
        if 'error' in case:
            with pytest.raises(JsonPatchError) as error:
                apply_json_patch(case['document'], case['patch'])
            assert error.value.reason == case['error'], case['id']
        else:
            assert apply_json_patch(case['document'], case['patch']).data == case['expected'], case['id']
        assert original == case['document'] and ops == case['patch']


@pytest.mark.parametrize('value', [None, True, False, 0, 0.5, '雪', [], {}, [None, {'x': 2}]])
def test_root_add_and_replace_are_real_json_values(value):
    for kind in ['add', 'replace']:
        r = apply_json_patch({'old': 1}, [{'op':kind,'path':'','value':value}])
        assert r.document_exists and r.data == value
        assert r.operations_applied == 1 and r.write_authorized is False


def test_root_removal_is_absent_not_null():
    r = apply_json_patch(None, [{'op':'remove','path':''}])
    assert r.document_exists is False
    with pytest.raises(JsonPatchError) as error: _ = r.data
    assert error.value.reason == 'document_absent'
    r = apply_json_patch(1, [{'op':'remove','path':''}, {'op':'add','path':'','value':None}])
    assert r.document_exists and r.data is None


def test_array_operations_use_the_previous_operation_result():
    source = ['a','b','c']
    result = apply_json_patch(source, [
        {'op':'add','path':'/1','value':'new'},
        {'op':'remove','path':'/0'},
        {'op':'replace','path':'/1','value':'B'},
        {'op':'move','from':'/0','path':'/2'},
        {'op':'copy','from':'/1','path':'/-'},
        {'op':'test','path':'','value':['B','c','new','c']}])
    assert result.data == ['B','c','new','c'] and source == ['a','b','c']


def test_unknown_members_are_inert_and_preserved():
    ops = [{'op':'add','path':'/x','value':1, 'from':False, 'unknown': {'op':'shell','command':'never'}}]
    p = JsonPatch(ops)
    assert p.data == ops and p.apply({}).data == {'x':1}


def test_all_input_and_result_containers_are_independent():
    source = {'a':[{'x':1}]}; ops = [{'op':'copy','from':'/a','path':'/b'}]
    program = JsonPatch(ops); ops[0]['path'] = '/wrong'
    result = program.apply(source); source['a'][0]['x'] = 100
    first = result.data; first['b'][0]['x'] = 99
    assert first['a'][0]['x'] == 1
    assert result.data == {'a':[{'x':1}],'b':[{'x':1}]}
    program.data.clear()
    assert len(program.data) == 1
    with pytest.raises(FrozenInstanceError): program._value = None


def test_copy_then_edit_does_not_change_source():
    result = apply_json_patch({'a':{'x':1}}, [
        {'op':'copy','from':'/a','path':'/b'},
        {'op':'replace','path':'/b/x','value':2}])
    assert result.data == {'a':{'x':1},'b':{'x':2}}


def test_move_same_location_requires_existing_source_and_is_noop():
    assert apply_json_patch({'x':1},[{'op':'move','from':'/x','path':'/x'}]).data == {'x':1}
    with pytest.raises(JsonPatchError): apply_json_patch({},[{'op':'move','from':'/x','path':'/x'}])


def test_move_into_own_descendant_is_rejected_without_changing_source():
    source = {'a':{'b':1}}
    with pytest.raises(JsonPatchError) as error:
        apply_json_patch(source,[{'op':'move','from':'/a','path':'/a/b/c'}])
    assert source == {'a':{'b':1}} and error.value.reason == 'move_into_descendant'


def test_pointer_escapes_empty_keys_and_numeric_object_members():
    source = {'':{'a/b':{'~key':1}}, '01':2, '-':3}
    r = apply_json_patch(source,[{'op':'replace','path':'//a~1b/~0key','value':4},
        {'op':'replace','path':'/01','value':5},{'op':'test','path':'/-','value':3}])
    assert r.data == {'':{'a/b':{'~key':4}},'01':5,'-':3}


@pytest.mark.parametrize('token', ['01','-1','+1',' 1','1.0','١','-', '', '9'*5000])
def test_invalid_array_indices_fail_without_mutation(token):
    source = [1,2]
    with pytest.raises(JsonPatchError): apply_json_patch(source,[{'op':'remove','path':'/'+token}])
    assert source == [1,2]


@pytest.mark.parametrize('item', [
    {'op':'remove','path':'/missing'}, {'op':'replace','path':'/missing','value':1},
    {'op':'add','path':'/missing/child','value':1}, {'op':'copy','from':'/missing','path':'/x'},
    {'op':'add','path':'/n/child','value':1}])
def test_missing_targets_and_parents_do_not_create_them(item):
    source = {'n':None}
    with pytest.raises(JsonPatchError): apply_json_patch(source,[item])
    assert source == {'n':None}


@pytest.mark.parametrize('patch', [None, {}, [1], [{'op':'eval','path':''}],
    [{'op':'add','path':'/x'}], [{'op':'move','path':'/x'}], [{'op':'remove','path':'x'}],
    [{'op':'remove','path':'/~2'}]])
def test_malformed_patch_is_rejected(patch):
    with pytest.raises(JsonPatchError): JsonPatch(patch)


@pytest.mark.parametrize('left,right', [(1,1.0), ({'b':1,'a':[]},{'a':[],'b':1.0}),([None,True],[None,True])])
def test_json_test_uses_json_equality(left,right):
    assert apply_json_patch(left,[{'op':'test','path':'','value':right}]).document_exists


@pytest.mark.parametrize('left,right', [(True,1),(False,0),([1,2],[2,1]),('1',1),(None,False),({'a':True},{'a':1})])
def test_json_test_rejects_python_boolean_number_equivalence(left,right):
    with pytest.raises(JsonPatchError) as error: apply_json_patch(left,[{'op':'test','path':'','value':right}])
    assert error.value.reason == 'test_failed'


def test_failure_stops_before_later_operations_and_keeps_original():
    source = {'x':1}
    with pytest.raises(JsonPatchError) as error:
        apply_json_patch(source,[{'op':'replace','path':'/x','value':2},
            {'op':'test','path':'/x','value':100}, {'op':'remove','path':'/missing'}])
    assert source == {'x':1}
    assert error.value.operation_index == 1 and error.value.pointer == '/patch/1/path'
    assert error.value.document_pointer == '/x'


def test_comfort_options_preserve_order_and_use_assignment_not_array_insertion():
    source = {'a':[1,2], 'obsolete':0}
    options = [('--set','/a/0=9'),('--set','/a/-={"x":"a=b"}'),
               ('--unset','/a/1'),('--set','/new=null'),('--unset','/obsolete')]
    patch = compile_field_patch(source,options)
    assert patch.data[0]['op'] == 'replace'
    assert patch.apply(source).data == {'a':[9,{'x':'a=b'}], 'new':None}
    assert source == {'a':[1,2], 'obsolete':0}


@pytest.mark.parametrize('argument',['/x=unquoted','/x=01','/x=NaN','/x=1 true','/x={"a":1,"a":2}','/x'])
def test_set_value_is_strict_json(argument):
    with pytest.raises(JsonPatchError): compile_field_patch({},[('--set',argument)])


def test_preview_update_requires_matching_explicit_preconditions():
    base = domain_value(); op = operation('update')
    preview = preview_update(base,op)
    assert preview.candidate['statement'] == 'Changed.'
    assert preview.candidate['revision'] == base['revision']
    assert preview.metadata_applied is False and preview.write_authorized is False
    assert preview.base_sha256 == canonical_json_sha256(base) and preview.changed
    assert base == domain_value()


@pytest.mark.parametrize('field,bad', [('expected_revision',2),('expected_sha256','0'*64),('target','SR-GOAL-'+'1'*26)])
def test_stale_or_wrong_update_is_rejected(field,bad):
    op=operation('update');op[field]=bad
    with pytest.raises(ChangePlanError): preview_update(domain_value(),op)


def test_revision_and_hash_when_both_supplied_must_both_match():
    base=domain_value();op=operation('update');op['expected_sha256']=canonical_json_sha256(base)
    assert preview_update(base,op).changed
    op['expected_revision']=2
    with pytest.raises(ChangePlanError): preview_update(base,op)
    op['expected_revision']=1;op['expected_sha256']='0'*64
    with pytest.raises(ChangePlanError): preview_update(base,op)


def test_update_without_precondition_is_never_allowed():
    op=operation('update');op.pop('expected_revision')
    with pytest.raises(ChangePlanError): preview_update(domain_value(),op)


@pytest.mark.parametrize('field',['id','id_scheme','artifact_type','schema_version','maturity','revision','created_at','created_by','updated_at','updated_by','relations'])
def test_protected_fields_cannot_be_modified_or_moved_away(field):
    base=domain_value()
    for item in [{'op':'add','path':'/'+field,'value':None},{'op':'move','from':'/'+field,'path':'/title'}]:
        op=operation('update');op['patch']=[item]
        with pytest.raises(ChangePlanError): preview_update(base,op)
    assert base==domain_value()


@pytest.mark.parametrize('kind',['evidence','baseline','proposal','relation_review'])
def test_special_workflows_are_not_replaced_by_generic_update(kind):
    base=record_value(kind)
    with pytest.raises(ChangePlanError):
        preview_update(base,{'op':'update','target':base['id'],'expected_revision':1,'patch':[]})


def test_final_candidate_schema_is_checked_after_the_patch():
    base=domain_value();op=operation('update')
    op['patch']=[{'op':'remove','path':'/statement'}]
    with pytest.raises(ChangePlanError): preview_update(base,op)
    op['patch'].append({'op':'add','path':'/statement','value':'Restored'})
    assert preview_update(base,op).candidate['statement']=='Restored'


def test_noop_patch_does_not_claim_new_revision_or_write_authority():
    op=operation('update');op['patch']=[{'op':'test','path':'/revision','value':1}]
    result=preview_update(domain_value(),op)
    assert not result.changed and result.candidate==domain_value()
    assert result.validation_scope=='update_candidate_only'
