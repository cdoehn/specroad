"""Configuration-chain failure boundaries and immutable effective selections."""
from copy import deepcopy
import sys

import pytest

from specroad.configurations import resolve_configuration
from specroad.graph.relations import SourceRelations
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from support.artifacts import artifact_bytes
from support.records import record_value


def configuration(index, **changes):
    return record_value('configuration', id='SR-CFG-' + format(index, '026X'),
                        name='Configuration ' + str(index), **changes)


def chain(length):
    values = [configuration(0)]
    for index in range(1, length):
        values.append(configuration(index, parent=values[-1]['id'], dimensions=[], selection={}))
    return values


def records(values):
    return [SourceRelations(artifact_bytes(value), path='configurations/' + value['id'] + '.json')
            for value in values]


def resolve(values, selected=None):
    return resolve_configuration(records(values), selected or values[-1]['id'])


@pytest.mark.parametrize('length', [3, 4, 9, 25])
@pytest.mark.parametrize('selected_index', [0, 1, -1])
def test_cycles_fail_at_the_selected_entry_without_partial_values(length, selected_index):
    values = chain(length)
    values[0]['parent'] = values[-1]['id']
    supplied = records(values)
    before = [record.source_bytes for record in supplied]
    chosen = values[selected_index]['id']
    with pytest.raises(ModelError) as caught:
        resolve_configuration(supplied, chosen)
    assert caught.value.reason == 'configuration_parent_cycle'
    assert caught.value.pointer == '/parent'
    assert caught.value.path == 'configurations/' + chosen + '.json'
    assert [record.source_bytes for record in supplied] == before


def test_tail_entering_a_cycle_reports_the_first_repeated_ancestor():
    values = chain(7)
    values[1]['parent'] = values[3]['id']
    with pytest.raises(ModelError) as caught:
        resolve(values)
    assert caught.value.reason == 'configuration_parent_cycle'
    assert caught.value.path == 'configurations/' + values[3]['id'] + '.json'


def test_deep_valid_chain_does_not_depend_on_python_recursion_depth():
    values = chain(sys.getrecursionlimit() + 50)
    result = resolve(values)
    assert result.effective_values == {'platform': 'linux'}
    assert [row['id'] for row in result.manifest['configurations']] == [v['id'] for v in values]


def test_deep_cycle_fails_as_configuration_error_without_recursion_error():
    values = chain(sys.getrecursionlimit() + 50)
    values[0]['parent'] = values[-1]['id']
    with pytest.raises(ModelError) as caught:
        resolve(values)
    assert caught.value.reason == 'configuration_parent_cycle'


def test_missing_grandparent_reports_the_record_with_the_broken_reference():
    values = chain(4)[1:]
    with pytest.raises(ModelError) as caught:
        resolve(values)
    assert caught.value.reason == 'configuration_parent_missing'
    assert caught.value.pointer == '/parent'
    assert caught.value.path == 'configurations/' + values[0]['id'] + '.json'


def test_missing_ancestor_prevents_child_defaults_from_producing_a_result():
    values = chain(3)[1:]
    values[-1]['dimensions'] = [{'name': 'edition', 'allowed_values': ['pro'], 'default': 'pro'}]
    supplied = records(values)
    before = [record.source_bytes for record in supplied]
    with pytest.raises(ModelError) as caught:
        resolve_configuration(supplied, values[-1]['id'])
    assert caught.value.reason == 'configuration_parent_missing'
    assert [record.source_bytes for record in supplied] == before


SCALARS = (
    ('null', None, 'null'), ('false', False, 'false'), ('true', True, 'true'),
    ('zero', 0, 'zero'), ('one', 1, 'one'), ('one-float', 1.0, 'one'),
    ('fraction', 1.5, 'fraction'), ('empty-string', '', 'empty-string'),
    ('numeric-string', '1', 'numeric-string'),
)
SCALAR_CASES = [pytest.param(allowed, choice, left_group == right_group, id=left + '--' + right)
                for left, allowed, left_group in SCALARS
                for right, choice, right_group in SCALARS]


@pytest.mark.parametrize('allowed,choice,accepted', SCALAR_CASES)
def test_inherited_scalar_membership_preserves_json_type_boundaries(allowed, choice, accepted):
    values = chain(3)
    values[0]['dimensions'] = [{'name': 'choice', 'allowed_values': [allowed]}]
    values[0]['selection'] = {'choice': allowed}
    values[-1]['selection'] = {'choice': choice}
    if accepted:
        actual = resolve(values).effective_values['choice']
        assert actual == choice
        assert type(actual) is type(choice)
    else:
        with pytest.raises(ModelError) as caught:
            resolve(values)
        assert caught.value.reason == 'invalid_dimension_selection'
        assert caught.value.path == 'configurations/' + values[-1]['id'] + '.json'
        assert caught.value.pointer == '/selection'


def test_child_can_complete_a_new_parent_dimension_before_default_fallback():
    values = chain(3)
    values[1]['dimensions'] = [{'name': 'edition', 'allowed_values': ['pro']}]
    values[2]['selection'] = {'edition': 'pro'}
    assert resolve(values).effective_values == {'platform': 'linux', 'edition': 'pro'}


def test_latest_descendant_override_wins_over_every_earlier_selection():
    values = chain(5)
    values[1]['selection'] = {'platform': 'windows'}
    values[3]['selection'] = {'platform': 'linux'}
    values[4]['selection'] = {'platform': 'windows'}
    assert resolve(values).effective_values == {'platform': 'windows'}


def test_child_default_does_not_replace_an_explicit_parent_selection():
    values = chain(3)
    values[0]['selection'] = {'platform': 'windows'}
    values[-1]['dimensions'] = deepcopy(values[0]['dimensions'])
    assert resolve(values).effective_values == {'platform': 'windows'}


def test_invalid_ancestor_selection_cannot_be_hidden_by_a_valid_child_override():
    values = chain(4)
    values[1]['selection'] = {'platform': 'invalid'}
    values[-1]['selection'] = {'platform': 'linux'}
    with pytest.raises(ModelError) as caught:
        resolve(values)
    assert caught.value.reason == 'invalid_dimension_selection'
    assert caught.value.path == 'configurations/' + values[1]['id'] + '.json'


def test_later_child_declaration_does_not_legitimize_an_unknown_parent_selection():
    values = chain(3)
    values[1]['selection'] = {'edition': 'pro'}
    values[2]['dimensions'] = [{'name': 'edition', 'allowed_values': ['pro']}]
    values[2]['selection'] = {'edition': 'pro'}
    with pytest.raises(ModelError) as caught:
        resolve(values)
    assert caught.value.reason == 'unknown_dimension'
    assert caught.value.path == 'configurations/' + values[1]['id'] + '.json'


@pytest.mark.parametrize('change', ['values', 'default', 'remove-default'])
def test_conflicting_ancestor_declaration_cannot_be_hidden_by_descendants(change):
    values = chain(4)
    dimension = deepcopy(values[0]['dimensions'][0])
    if change == 'values':
        dimension['allowed_values'] = ['linux']
    elif change == 'default':
        dimension['default'] = 'windows'
    else:
        del dimension['default']
    values[1]['dimensions'] = [dimension]
    values[3]['dimensions'] = deepcopy(values[0]['dimensions'])
    supplied = records(values)
    before = [record.source_bytes for record in supplied]
    with pytest.raises(ModelError) as caught:
        resolve_configuration(supplied, values[-1]['id'])
    assert caught.value.reason == 'inherited_dimension_changed'
    assert caught.value.pointer == '/dimensions/0'
    assert caught.value.path == 'configurations/' + values[1]['id'] + '.json'
    assert [record.source_bytes for record in supplied] == before


def test_json_equivalent_numeric_declaration_is_not_a_dimension_change():
    values = chain(2)
    values[0]['dimensions'] = [{'name': 'number', 'allowed_values': [1], 'default': 1}]
    values[0]['selection'] = {}
    values[1]['dimensions'] = [{'name': 'number', 'allowed_values': [1.0], 'default': 1.0}]
    result = resolve(values)
    assert result.effective_values == {'number': 1}
    assert result.dimensions == values[0]['dimensions']


@pytest.mark.parametrize('index', [0, 1, 2])
@pytest.mark.parametrize('applicability', [None, False, {}, {'expression': 'ignored'}])
def test_any_present_applicability_field_in_the_chain_is_rejected(index, applicability):
    values = chain(3)
    values[index]['applicability'] = applicability
    with pytest.raises(ModelError) as caught:
        resolve(values)
    assert caught.value.pointer == '/applicability'
    assert caught.value.path == 'configurations/' + values[index]['id'] + '.json'


def test_parent_cycle_outside_the_selected_chain_does_not_change_its_scope():
    values = chain(3)
    values[0]['parent'] = values[-1]['id']
    selected = configuration(9)
    result = resolve(values + [selected])
    assert result.manifest['configurations'] == [
        {'id': selected['id'], 'revision': 1, 'sha256': canonical_json_sha256(selected)}]
    assert result.validation_scope == 'supplied_root_configuration_only'


def test_missing_parent_outside_the_selected_chain_is_not_resolved():
    unrelated = configuration(1, parent=configuration(2)['id'], dimensions=[], selection={})
    selected = configuration(9)
    assert resolve([unrelated, selected]).sha256 == resolve([selected]).sha256


def test_parent_cache_cannot_replace_its_original_selection():
    values = chain(2)
    supplied = records(values)
    supplied[0].data['selection']['platform'] = 'windows'
    result = resolve_configuration(supplied, values[-1]['id'])
    assert result.effective_values == {'platform': 'linux'}
    assert result.manifest['configurations'][0]['sha256'] == canonical_json_sha256(values[0])


def test_ancestor_revision_is_bound_even_when_its_selection_is_overridden():
    values = chain(4)
    values[-1]['selection'] = {'platform': 'windows'}
    original = resolve(values)
    values[1]['revision'] = 2
    revised = resolve(values)
    assert revised.effective_values == original.effective_values
    assert revised.sha256 != original.sha256


def test_separate_resolutions_do_not_reuse_stale_parent_values():
    values = chain(2)
    before = resolve(values)
    values[0]['selection'] = {'platform': 'windows'}
    after = resolve(values)
    assert before.effective_values == {'platform': 'linux'}
    assert after.effective_values == {'platform': 'windows'}
    assert before.sha256 != after.sha256
