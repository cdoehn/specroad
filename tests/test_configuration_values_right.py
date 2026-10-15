"""Acceptance tables for configuration selection, defaults and field boundaries."""
import pytest

from specroad.configurations import resolve_configuration
from specroad.graph.relations import SourceRelations
from specroad.model.errors import ModelError
from specroad.storage.record_artifact import RecordArtifact
from support.artifacts import artifact_bytes
from support.records import record_value, ref


# Explicit JSON equivalence classes: numbers 1 and 1.0 are the same value;
# boolean true and the string "1" are different classes.
SCALARS = (
    ('null', None, 'null'), ('false', False, 'false'), ('true', True, 'true'),
    ('zero', 0, 'zero'), ('one', 1, 'one'), ('one-float', 1.0, 'one'),
    ('fraction', 1.5, 'fraction'), ('empty-string', '', 'empty-string'),
    ('numeric-string', '1', 'numeric-string'),
)
SCALAR_CASES = [
    pytest.param(allowed, selected, allowed_group == selected_group, id=a + '--' + b)
    for a, allowed, allowed_group in SCALARS
    for b, selected, selected_group in SCALARS
]


def resolve(value):
    record = SourceRelations(artifact_bytes(value))
    return resolve_configuration([record], record.identity.id)


@pytest.mark.parametrize('field', ['selection', 'default'])
@pytest.mark.parametrize('allowed,selected,accepted', SCALAR_CASES)
def test_scalar_acceptance_matrix(field, allowed, selected, accepted):
    dimension = {'name': 'choice', 'allowed_values': [allowed]}
    selection = {'choice': selected} if field == 'selection' else {}
    if field == 'default':
        dimension['default'] = selected
    value = record_value('configuration', dimensions=[dimension], selection=selection)
    if accepted:
        actual = resolve(value).effective_values['choice']
        assert actual == selected
        assert type(actual) is type(selected)
    else:
        with pytest.raises(ModelError) as caught:
            resolve(value)
        assert caught.value.reason == ('invalid_dimension_selection' if field == 'selection'
                                       else 'invalid_dimension_default')


@pytest.mark.parametrize('selected', [None, False, 0, '', 'linux'])
def test_unknown_dimension_never_uses_a_declared_default(selected):
    value = record_value('configuration', selection={'unknown': selected})
    with pytest.raises(ModelError) as caught:
        resolve(value)
    assert caught.value.reason == 'unknown_dimension'
    assert caught.value.pointer == '/selection'


@pytest.mark.parametrize('explicit', [False, True])
@pytest.mark.parametrize('name', ['\0', 'prefix\0suffix'])
def test_dimension_name_rejection_is_the_same_for_defaults_and_selection(name, explicit):
    value = record_value('configuration', dimensions=[
        {'name': name, 'allowed_values': ['value'], 'default': 'value'}],
        selection={name: 'value'} if explicit else {})
    raw = artifact_bytes(value)
    for operation in (lambda: RecordArtifact(raw), lambda: resolve(value)):
        with pytest.raises(ModelError) as caught:
            operation()
        assert caught.value.reason == 'schema_not'
        assert caught.value.pointer == '/dimensions/0/name'


@pytest.mark.parametrize('name', ['a/b', 'a~b', ' platform ', '東京', 'e\u0301'])
def test_dimension_names_are_exact_keys_not_json_pointer_expressions(name):
    value = record_value('configuration', dimensions=[{'name': name, 'allowed_values': ['value']}],
                         selection={name: 'value'})
    assert resolve(value).effective_values == {name: 'value'}


def test_control_character_in_a_value_is_not_a_dimension_name():
    value = record_value('configuration', dimensions=[{'name': 'choice', 'allowed_values': ['\0']}],
                         selection={'choice': '\0'})
    assert resolve(value).effective_values == {'choice': '\0'}


@pytest.mark.parametrize('field', ['selection', 'default'])
@pytest.mark.parametrize('value', [[], {}, ['linux'], {'platform': 'linux'}])
def test_container_choices_are_not_json_scalars(field, value):
    dimension = {'name': 'platform', 'allowed_values': ['linux']}
    selection = {'platform': value} if field == 'selection' else {}
    if field == 'default':
        dimension['default'] = value
    with pytest.raises(ModelError) as caught:
        resolve(record_value('configuration', dimensions=[dimension], selection=selection))
    assert caught.value.reason == 'schema_any_of'
    assert caught.value.pointer == ('/selection/platform' if field == 'selection' else '/dimensions/0/default')


@pytest.mark.parametrize('choices', [[], [[], 'linux'], [{}, 'linux'], ['linux', 'linux'], [1, 1.0]])
def test_invalid_allowed_value_sets_are_rejected(choices):
    value = record_value('configuration', dimensions=[{'name': 'choice', 'allowed_values': choices}],
                         selection={'choice': 'linux'})
    with pytest.raises(ModelError):
        resolve(value)


def test_boolean_and_number_can_be_distinct_allowed_values():
    for selected in (False, 0, True, 1):
        value = record_value('configuration', dimensions=[
            {'name': 'choice', 'allowed_values': [False, 0, True, 1]}], selection={'choice': selected})
        actual = resolve(value).effective_values['choice']
        assert actual == selected
        assert type(actual) is type(selected)


@pytest.mark.parametrize('dimensions', [None, False, {}, 'platform'])
def test_dimensions_require_a_declared_sequence(dimensions):
    with pytest.raises(ModelError) as caught:
        resolve(record_value('configuration', dimensions=dimensions))
    assert caught.value.reason == 'schema_type'
    assert caught.value.pointer == '/dimensions'


@pytest.mark.parametrize('selection', [None, False, [], 'linux'])
def test_selection_requires_an_object(selection):
    with pytest.raises(ModelError) as caught:
        resolve(record_value('configuration', selection=selection))
    assert caught.value.reason == 'schema_type'
    assert caught.value.pointer == '/selection'


@pytest.mark.parametrize('name', [None, False, 0, [], {}])
def test_configuration_names_require_strings(name):
    with pytest.raises(ModelError) as caught:
        resolve(record_value('configuration', name=name))
    assert caught.value.reason == 'schema_type'
    assert caught.value.pointer == '/name'


@pytest.mark.parametrize('name', ['', ' ', '\n\t'])
def test_configuration_names_cannot_be_empty(name):
    with pytest.raises(ModelError):
        resolve(record_value('configuration', name=name))


@pytest.mark.parametrize('field', ['name', 'allowed_values'])
def test_incomplete_dimension_declarations_are_not_synthesized(field):
    dimension = {'name': 'platform', 'allowed_values': ['linux']}
    dimension.pop(field)
    with pytest.raises(ModelError) as caught:
        resolve(record_value('configuration', dimensions=[dimension], selection={'platform': 'linux'}))
    assert caught.value.reason == 'missing_field'
    assert caught.value.pointer == '/dimensions/0/' + field


def test_a_later_invalid_dimension_does_not_return_a_partial_selection():
    value = record_value('configuration', dimensions=[
        {'name': 'valid', 'allowed_values': ['ok'], 'default': 'ok'},
        {'name': 'invalid', 'allowed_values': ['ok']}], selection={'invalid': 'wrong'})
    before = artifact_bytes(value)
    with pytest.raises(ModelError) as caught:
        resolve(value)
    assert caught.value.reason == 'invalid_dimension_selection'
    assert artifact_bytes(value) == before


def test_invalid_unselected_configuration_is_not_a_valid_inventory():
    first = SourceRelations(artifact_bytes(record_value('configuration')))
    invalid = SourceRelations(artifact_bytes(record_value('configuration', id=ref('CFG', '1'),
                              name='Invalid', selection={'platform': 'unknown'})))
    with pytest.raises(ModelError) as caught:
        resolve_configuration([first, invalid], first.identity.id)
    assert caught.value.reason == 'invalid_dimension_selection'


def test_empty_inventory_cannot_resolve_a_configuration():
    with pytest.raises(ModelError) as caught:
        resolve_configuration([], ref('CFG'))
    assert caught.value.reason == 'configuration_missing'


def test_source_location_survives_configuration_field_rejection():
    value = record_value('configuration', selection={'platform': 'unknown'})
    path = 'spec/configurations/' + value['id'] + '.json'
    record = SourceRelations(artifact_bytes(value), path=path)
    with pytest.raises(ModelError) as caught:
        resolve_configuration([record], record.identity.id)
    assert caught.value.path == path
    assert caught.value.pointer == '/selection'


def test_source_byte_replacement_is_revalidated_before_using_cached_identity():
    record = SourceRelations(artifact_bytes(record_value('configuration')))
    invalid = artifact_bytes(record_value('configuration', selection={'platform': 'unknown'}))
    object.__setattr__(record, 'source_bytes', invalid)
    with pytest.raises(ModelError) as caught:
        resolve_configuration([record], record.identity.id)
    assert caught.value.reason == 'invalid_dimension_selection'
