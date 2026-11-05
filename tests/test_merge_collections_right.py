"""17.d.R: ordered semantics, typed identities and strict source boundaries."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
from unittest.mock import patch

import pytest

from specroad.merge import merge_fields, merge_attachments
from specroad.model._schema import validate_builtin
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.domain_schemas import domain_schema
from specroad.model.record_schemas import record_schema
from specroad.model.errors import ModelError
from specroad.merge.schema_collections import collection_rules
from support.domain import domain_value
from support.records import record_value
from test_merge_collections import merge


@pytest.mark.parametrize('ours,theirs', [
    (['a','b','ours'], ['a','b','theirs']),
    (['b','a'], ['a','b','theirs']),
    (['a'], ['b']),
    (['b','a'], ['b','a','extra']),
])
@pytest.mark.parametrize('swap', [False,True])
def test_concurrent_ordered_edits_never_sort_align_or_choose_a_winner(ours, theirs, swap):
    if swap:
        ours, theirs = theirs, ours
    values = [domain_value('scenario', main_flow=value) for value in (['a','b'], ours, theirs)]
    result = merge(values, domain_schema('scenario')); conflict, = result.conflicts
    assert conflict.kind == 'ordered_sequence_change' and conflict.pointer == '/main_flow'
    assert [v.value for v in (conflict.base,conflict.ours,conflict.theirs)] == [['a','b'],ours,theirs]
    with pytest.raises(ModelError):
        _ = result.value


@pytest.mark.parametrize('ours,theirs', [(['b','a'],['a','b']), (['a','b'],['b','a']), (['b','a'],['b','a'])])
def test_unambiguous_ordered_change_keeps_the_exact_chosen_sequence(ours, theirs):
    values = [domain_value('scenario', main_flow=value) for value in (['a','b'], ours, theirs)]
    assert merge(values, domain_schema('scenario')).value['main_flow'] == ['b','a']


def test_object_fields_named_id_do_not_imply_a_set():
    values = [domain_value('requirement', thresholds=value) for value in (
        [{'id':'x','limit':1}], [{'id':'x','limit':1},{'id':'y','limit':2}], [{'id':'x','limit':1},{'id':'z','limit':3}])]
    conflict, = merge(values, domain_schema('requirement')).conflicts
    assert conflict.kind == 'ordered_sequence_change' and conflict.pointer == '/thresholds'


def test_undeclared_extension_arrays_do_not_inherit_tags_semantics():
    base = domain_value('goal', extensions={'vendor.test':{'tags':['base']}})
    ours, theirs = deepcopy(base), deepcopy(base)
    ours['extensions']['vendor.test']['tags'].append('ours')
    theirs['extensions']['vendor.test']['tags'].append('theirs')
    result = merge([base,ours,theirs], domain_schema('goal'))
    assert result.conflicts[0].kind == 'ordered_sequence_change'
    assert result.conflicts[0].pointer == '/extensions/vendor.test/tags'


def test_missing_whole_set_and_changed_set_are_distinct_from_empty():
    base = domain_value('goal', tags=['base']); ours, theirs = deepcopy(base), deepcopy(base)
    del ours['tags']; theirs['tags'].append('theirs')
    result = merge([base,ours,theirs], domain_schema('goal')); conflict, = result.conflicts
    assert conflict.pointer == '/tags' and conflict.kind == 'remove_edit'
    assert conflict.ours.present is False and conflict.theirs.value == ['base','theirs']
    ours['tags'] = []
    assert merge([base,ours,theirs], domain_schema('goal')).value['tags'] == ['theirs']


def test_new_set_on_both_sides_combines_without_synthesizing_a_base():
    base = domain_value('goal'); base.pop('tags',None)
    ours, theirs = deepcopy(base), deepcopy(base); ours['tags'] = ['left']; theirs['tags'] = ['right']
    assert merge([base,ours,theirs], domain_schema('goal')).value['tags'] == ['left','right']


def test_typed_scalar_keys_keep_boolean_number_and_null_separate():
    base = record_value('configuration', dimensions=[{'name':'value','allowed_values':[None]}], selection={})
    ours, theirs = deepcopy(base), deepcopy(base)
    ours['dimensions'][0]['allowed_values'].append(True)
    theirs['dimensions'][0]['allowed_values'].append(1)
    result = merge([base,ours,theirs], record_schema('configuration'))
    assert jcs(result.value['dimensions'][0]['allowed_values']) == b'[1,null,true]'


@pytest.mark.parametrize('position', range(3))
@pytest.mark.parametrize('duplicate', [[1,1.0], [0,-0.0], ['same','same']])
def test_nested_duplicate_keys_cannot_hide_inside_an_unchanged_outer_set(position, duplicate):
    values = [record_value('configuration') for _ in range(3)]
    values[position]['dimensions'][0]['allowed_values'] = duplicate
    with pytest.raises(ModelError) as caught:
        merge(values, record_schema('configuration'))
    assert caught.value.reason == 'duplicate_merge_set_key'
    assert caught.value.pointer == '/dimensions/0/allowed_values'


def test_unicode_identity_is_not_normalized_or_casefolded():
    values = [domain_value('goal', tags=value) for value in ([], ['é','A'], ['e\u0301','a'])]
    assert merge(values, domain_schema('goal')).value['tags'] == ['A','a','e\u0301','é']


def test_nested_set_reordering_does_not_mask_the_other_sides_real_edit():
    base = record_value('configuration'); ours, theirs = deepcopy(base), deepcopy(base)
    ours['dimensions'][0]['allowed_values'].reverse()
    theirs['dimensions'][0]['default'] = 'windows'
    result = merge([base,ours,theirs], record_schema('configuration'))
    assert result.value['dimensions'] == theirs['dimensions']


def test_multiple_key_conflicts_are_stable_and_do_not_invent_shared_array_indices():
    base = record_value('configuration', dimensions=[
        {'name':'z/~','allowed_values':['a','b'],'default':'a'},
        {'name':'a','allowed_values':['a','b'],'default':'a'}], selection={})
    ours, theirs = deepcopy(base), deepcopy(base)
    ours['dimensions'] = []
    theirs['dimensions'].reverse()
    for item in theirs['dimensions']:
        item['default'] = 'b'
    result = merge([base,ours,theirs], record_schema('configuration')); conflict, = result.conflicts
    assert conflict.pointer == '/dimensions'
    assert [key.value for key in conflict.element_keys] == ['a','z/~']
    assert conflict.base.value == base['dimensions'] and conflict.theirs.value == theirs['dimensions']
    detached = conflict.theirs.value; detached.clear(); theirs['dimensions'].clear()
    assert len(conflict.theirs.value) == 2
    with pytest.raises(FrozenInstanceError):
        conflict.element_keys = ()


def test_removal_of_one_key_does_not_block_an_independent_other_key_change():
    base = record_value('configuration', dimensions=[
        {'name':'first','allowed_values':['a']}, {'name':'second','allowed_values':['b','c']}], selection={})
    ours, theirs = deepcopy(base), deepcopy(base)
    ours['dimensions'].pop(0); theirs['dimensions'][1]['default'] = 'c'
    assert merge([base,ours,theirs], record_schema('configuration')).value['dimensions'] == [
        {'name':'second','allowed_values':['b','c'],'default':'c'}]


@pytest.mark.parametrize('invalid', [None, ['not-an-object'], [{'allowed_values':['x']}], [{'name':{},'allowed_values':['x']}]])
def test_missing_or_composite_keys_and_invalid_collection_types_are_rejected(invalid):
    values = [record_value('configuration') for _ in range(3)]; values[1]['dimensions'] = invalid
    with pytest.raises(ModelError):
        merge(values, record_schema('configuration'))


@pytest.mark.parametrize('annotation', [None, True, [], {}, {'kind':'bag','key':''},
    {'kind':'set'}, {'kind':'ordered','key':''}, {'kind':'set','key':'name'},
    {'kind':'set','key':'/bad~2'}, {'kind':'set','key':False}, {'kind':'set','key':'','extra':1}])
def test_schema_vocabulary_rejects_malformed_collection_annotations(annotation):
    schema = {'type':'array','items':{'type':'string'},'x-specroad-merge':annotation}
    with pytest.raises(ValueError):
        validate_builtin([], schema)


def test_annotation_is_not_accepted_on_non_array_or_as_hidden_conditional_rule():
    with pytest.raises(ValueError):
        validate_builtin('x', {'type':'string','x-specroad-merge':{'kind':'set','key':''}})
    node = {'type':'array','x-specroad-merge':{'kind':'set','key':''}}
    for key in ('anyOf','not','additionalProperties'):
        schema = {key:[node] if key == 'anyOf' else node}
        with pytest.raises(ValueError):
            collection_rules(schema)


def test_conflicting_unconditional_schema_rules_fail_closed():
    schema = {'allOf':[{'type':'array','x-specroad-merge':{'kind':'set','key':''}},
                       {'type':'array','x-specroad-merge':{'kind':'ordered'}}]}
    with pytest.raises(ValueError):
        collection_rules(schema)


def test_deep_unconstrained_data_keeps_the_iterative_field_boundary():
    nested = {'value':1}
    for _ in range(1100):
        nested = {'child':nested}
    base = domain_value('goal', tags=[], extensions={'vendor.test':nested})
    ours, theirs = {**base,'tags':['left']}, {**base,'tags':['right']}
    result = merge_fields(base,ours,theirs,schema_id=domain_schema('goal')['$id'])
    assert result.value['tags'] == ['left','right']
    assert jcs(result.value['extensions']) == jcs(base['extensions'])


def test_computations_have_no_filesystem_process_or_network_side_effects():
    value = domain_value('goal', tags=['a']); schema_id = domain_schema('goal')['$id']
    # Warm the trusted built-in registry; import I/O is not project I/O.
    from specroad.model.schema_catalog import SchemaCatalog
    SchemaCatalog().get(schema_id)
    with patch('builtins.open',side_effect=AssertionError('file access')), \
         patch('os.open',side_effect=AssertionError('file access')), \
         patch('subprocess.Popen',side_effect=AssertionError('process')), \
         patch('socket.socket',side_effect=AssertionError('network')):
        assert merge_fields(value,value,value,schema_id=schema_id).value == value
        assert merge_attachments({}, {'attachments/x':b'bytes'}, {}).files == {'attachments/x':b'bytes'}


@pytest.mark.parametrize('first,second', [
    ('attachments/a.bin','attachments/A.bin'),
    ('attachments/Dir/a','attachments/dir/b'),
    ('attachments/a','attachments/a/child'),
    ('attachments/A','attachments/a/child'),
    ('attachments/straße','attachments/STRASSE'),
])
@pytest.mark.parametrize('same_source', [False,True])
def test_portable_aliases_and_file_descendants_are_rejected_across_all_sources(first, second, same_source):
    values = ({}, {first:b'a',second:b'b'}, {}) if same_source else ({first:b'a'}, {first:b'a'}, {second:b'b'})
    with pytest.raises(ModelError) as caught:
        merge_attachments(*values)
    assert caught.value.reason == 'merge_attachment_path_collision'


def test_case_distinct_payload_bytes_are_not_unicode_or_text_normalized():
    result = merge_attachments({'attachments/text':b'old'},
        {'attachments/text':'é'.encode()}, {'attachments/text':'e\u0301'.encode()})
    conflict, = result.conflicts
    assert conflict.kind == 'attachment_binary_change'
    assert conflict.ours_sha256 == sha256('é'.encode()).hexdigest()
    assert conflict.theirs_sha256 == sha256('e\u0301'.encode()).hexdigest()


@pytest.mark.parametrize('position', range(3))
def test_attachment_inputs_do_not_invoke_foreign_mapping_hooks(position):
    class Foreign(dict):
        def items(self):
            raise AssertionError('foreign hook executed')
    values = [{}, {}, {}]; values[position] = Foreign()
    with pytest.raises(ModelError) as caught:
        merge_attachments(*values)
    assert caught.value.reason == 'invalid_merge_attachment_source'
