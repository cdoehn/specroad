"""17.c.R: explicit three-way oracles, strict values and safe conflict boundaries."""
from dataclasses import FrozenInstanceError
from decimal import Decimal
import builtins
import io
import os
import socket
import subprocess

import pytest

from specroad.merge import merge_fields
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.errors import ModelError
from test_merge_fields import assert_value


# Each entry spells out actual objects: absence is never a JSON null proxy.
@pytest.mark.parametrize('base,ours,theirs,expected', [
    ({}, {}, {}, {}),
    ({}, {'f': None}, {}, {'f': None}),
    ({}, {}, {'f': None}, {'f': None}),
    ({}, {'f': None}, {'f': None}, {'f': None}),
    ({'f': None}, {}, {'f': None}, {}),
    ({'f': None}, {'f': None}, {}, {}),
    ({'f': None}, {}, {}, {}),
    ({'f': None}, {'f': ''}, {'f': None}, {'f': ''}),
    ({'f': None}, {'f': None}, {'f': False}, {'f': False}),
    ({'f': 0}, {'f': False}, {'f': 0}, {'f': False}),
    ({'f': False}, {'f': False}, {'f': 0}, {'f': 0}),
    ({'f': ''}, {'f': 'null'}, {'f': ''}, {'f': 'null'}),
    ({'f': {}}, {'f': {}}, {'f': {}}, {'f': {}}),
    ({'f': {'a': 1}}, {'f': {}}, {'f': {'a': 1}}, {'f': {}}),
    ({'f': {'a': 1}}, {}, {'f': {'a': 1}}, {}),
    ({'f': {'a': 1}}, {'f': {'a': 1}}, {}, {}),
    ({'f': {'a': 1}}, {}, {}, {}),
    ({'f': None}, {'f': {'x': 1}}, {'f': {'x': 1.0}}, {'f': {'x': 1}}),
    ({}, {'f': {}}, {'f': {}}, {'f': {}}),
    ({}, {'f': {}}, {'f': {'x': 1}}, {'f': {'x': 1}}),
    ({'f': [1]}, {'f': [2, 1]}, {'f': [2.0, 1.0]}, {'f': [2, 1]}),
    ({'f': {'a': None, 'b': 1}}, {'f': {'b': 1}}, {'f': {'a': None, 'b': 2}}, {'f': {'b': 2}}),
], ids=[f'matrix-{i:02d}' for i in range(22)])
def test_missing_null_scalar_and_object_success_matrix(base, ours, theirs, expected):
    assert_value(base, ours, theirs, expected)
    assert_value(base, theirs, ours, expected)


@pytest.mark.parametrize('base,ours,theirs,kind', [
    ({}, {'f': None}, {'f': ''}, 'type_change'),
    ({}, {'f': 0}, {'f': False}, 'type_change'),
    ({'f': None}, {}, {'f': ''}, 'remove_edit'),
    ({'f': None}, {'f': 'null'}, {}, 'remove_edit'),
    ({'f': 'old'}, {'f': 'ours'}, {'f': 'theirs'}, 'scalar_change'),
    ({'f': 1}, {'f': 2}, {'f': 3}, 'scalar_change'),
    ({'f': 1}, {'f': True}, {'f': 2}, 'type_change'),
    ({'f': True}, {'f': 1}, {'f': False}, 'type_change'),
    ({'f': 1}, {'f': None}, {'f': ''}, 'type_change'),
    ({'f': {}}, {}, {'f': {'x': 1}}, 'remove_edit'),
    ({'f': {'x': 1}}, {}, {'f': {'x': 2}}, 'remove_edit'),
    ({'f': {'x': 1}}, {}, {'f': {}}, 'remove_edit'),
    ({'f': {'x': 1}}, {'f': None}, {'f': {'x': 2}}, 'type_change'),
    ({'f': 0}, {'f': {'x': 1}}, {'f': {'y': 2}}, 'type_change'),
    ({'f': None}, {'f': [1]}, {'f': [2]}, 'type_change'),
    ({'f': []}, {'f': [1]}, {'f': [2]}, 'collection_semantics_required'),
], ids=[f'conflict-{i:02d}' for i in range(16)])
def test_conflict_matrix_keeps_all_original_values_without_guessing_a_winner(base, ours, theirs, kind):
    for left, right in ((ours, theirs), (theirs, ours)):
        result = merge_fields(base, left, right)
        conflict, = result.conflicts
        assert conflict.pointer == '/f' and conflict.kind == kind
        for observation, original in zip((conflict.base, conflict.ours, conflict.theirs), (base, left, right)):
            assert observation.present == ('f' in original)
            if observation.present:
                assert jcs(observation.value) == jcs(original['f'])
            else:
                with pytest.raises(ModelError):
                    _ = observation.value
        assert result.merged is False
        with pytest.raises(ModelError) as caught:
            _ = result.value
        assert caught.value.reason == 'unresolved_field_merge'


def test_all_independent_conflicts_have_unambiguous_rfc6901_locations():
    base = {'': {'/~': 0}, 'a': {'x': None}, 'z': 1}
    ours = {'z': 2, 'a': {'x': 1}, '': {'/~': 1}}
    theirs = {'a': {'x': 2}, '': {'/~': 2}, 'z': 3}
    result = merge_fields(base, ours, theirs)
    assert [c.pointer for c in result.conflicts] == ['//~1~0', '/a/x', '/z']
    assert [c.kind for c in result.conflicts] == ['scalar_change'] * 3
    reordered = merge_fields(dict(reversed(list(base.items()))), theirs, ours)
    assert [c.pointer for c in reordered.conflicts] == ['//~1~0', '/a/x', '/z']
    assert jcs([c.ours.value for c in result.conflicts]) == b'[1,1,2]'


def test_root_scalars_use_empty_pointer_and_null_remains_a_valid_result():
    assert_value('old', None, 'old', None)
    result = merge_fields(0, 1, 2)
    conflict, = result.conflicts
    assert conflict.pointer == '' and conflict.kind == 'scalar_change'
    assert [c.value for c in (conflict.base, conflict.ours, conflict.theirs)] == [0, 1, 2]


def test_no_unicode_normalization_or_boolean_number_coercion_in_nested_values():
    assert_value({}, {'é': 1}, {'e\u0301': 2}, {'é': 1, 'e\u0301': 2})
    result = merge_fields({'f': ['old']}, {'f': [True]}, {'f': [1]})
    assert result.merged is False
    assert result.conflicts[0].ours.value == [True]
    assert result.conflicts[0].theirs.value == [1]
    result = merge_fields({'f': ''}, {'f': 'é'}, {'f': 'e\u0301'})
    assert result.conflicts[0].kind == 'scalar_change'


@pytest.mark.parametrize('role', range(3))
@pytest.mark.parametrize('invalid,reason', [
    (b'bytes', 'unsupported_json_type'),
    ((1, 2), 'unsupported_json_type'),
    ({1: 'key'}, 'string_key_required'),
    ({'f': Decimal('1')}, 'unsupported_json_type'),
    ({'f': float('nan')}, 'nonfinite_number'),
    ({'f': float('inf')}, 'nonfinite_number'),
    ({'f': 9007199254740993}, 'number_roundtrip_loss'),
    ({'f': '\ud800'}, 'invalid_unicode'),
], ids=['bytes','tuple','key','decimal','nan','infinity','precision','unicode'])
def test_every_role_is_validated_even_when_other_sides_are_identical(role, invalid, reason):
    inputs = [{'f': 'same'} for _ in range(3)]; inputs[role] = invalid
    with pytest.raises(ModelError) as caught:
        merge_fields(*inputs)
    assert caught.value.reason == reason


def test_cycles_fail_but_shared_json_subobjects_are_owned_independently():
    cyclic = {}; cyclic['self'] = cyclic
    with pytest.raises(ModelError) as caught:
        merge_fields({}, cyclic, {})
    assert caught.value.reason == 'cyclic_json'
    shared = {'v': 1}
    result = assert_value({}, {'a': shared, 'b': shared}, {}, {'a': {'v': 1}, 'b': {'v': 1}})
    shared['v'] = 99
    detached = result.value; detached['a']['v'] = 88
    assert detached['b']['v'] == 1 and result.value == {'a': {'v': 1}, 'b': {'v': 1}}


def test_foreign_conversion_equality_and_iteration_hooks_are_not_called():
    called = []

    class Foreign:
        def __eq__(self, other):
            called.append('eq'); return True
        def __str__(self):
            called.append('str'); return '{}'

    class ForeignDict(dict):
        def __iter__(self):
            called.append('iter'); return super().__iter__()

    for bad in (Foreign(), ForeignDict(f=1)):
        with pytest.raises(ModelError) as caught:
            merge_fields({}, {'f': bad}, {})
        assert caught.value.reason == 'unsupported_json_type'
    assert called == []


def nested(value, depth):
    for _ in range(depth):
        value = {'child': value}
    return value


def test_deep_recursion_semantics_do_not_depend_on_python_recursion_limit():
    depth = 1500
    base = nested({'a': 0, 'b': 0}, depth)
    ours = nested({'a': 1, 'b': 0}, depth)
    theirs = nested({'a': 0, 'b': 2}, depth)
    result = merge_fields(base, ours, theirs)
    assert result.merged and result.conflicts == ()
    value = result.value
    for _ in range(depth):
        value = value['child']
    assert value == {'a': 1, 'b': 2}
    result = merge_fields(base, ours, nested({'a': 3, 'b': 0}, depth))
    conflict, = result.conflicts
    assert conflict.pointer == '/child' * depth + '/a'
    assert conflict.base.value == 0 and conflict.ours.value == 1 and conflict.theirs.value == 3


def test_deep_array_values_remain_owned_when_atomic_selection_is_unambiguous():
    value = None
    for _ in range(1500):
        value = [value]
    result = merge_fields({}, {'f': value}, {})
    target = result.value['f']
    for _ in range(1500):
        assert type(target) is list and len(target) == 1
        target = target[0]
    assert target is None


def test_input_and_conflict_mutation_cannot_rewrite_observations():
    base, ours, theirs = {'f': {'v': 1}}, {'f': {'v': 2}}, {'f': None}
    result = merge_fields(base, ours, theirs)
    conflict, = result.conflicts
    for value in (base, ours, theirs):
        value.clear()
    assert conflict.base.value == {'v': 1} and conflict.ours.value == {'v': 2}
    assert conflict.theirs.value is None
    with pytest.raises(FrozenInstanceError):
        conflict.kind = 'resolved'
    with pytest.raises(FrozenInstanceError):
        conflict.ours.value = {'forged': True}


def test_field_merge_uses_no_files_processes_network_or_environment(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Unexpected side effect in pure field merge')

    for owner, name in ((builtins, 'open'), (io, 'open'), (os, 'open'),
                        (os, 'getenv'), (subprocess, 'Popen'), (socket, 'socket')):
        monkeypatch.setattr(owner, name, forbidden)
    result = merge_fields({'f': 1, 'g': 2}, {'f': 3, 'g': 2}, {'f': 1, 'g': 4})
    assert result.value == {'f': 3, 'g': 4} and result.merged
    result = merge_fields({'f': 1}, {}, {'f': 2})
    assert result.conflicts[0].kind == 'remove_edit' and not result.write_authorized
