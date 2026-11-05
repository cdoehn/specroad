"""17.c.W: recursive field values are combined without publishing a resource."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json

import pytest

from specroad.merge import merge_fields, build_merge_inventory
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.errors import ModelError
from support.read_only import inventory
from test_merge_inventory import bind_files, row_for, PLAN_ID, ROLES
from test_merge_sources import read_only_sources
from test_project_bundle import project


def assert_value(base, ours, theirs, expected):
    before = [jcs(value) for value in (base, ours, theirs)]
    result = merge_fields(base, ours, theirs)
    assert result.merged is True and result.conflicts == ()
    assert jcs(result.value) == jcs(expected)
    assert result.ready is False and result.write_authorized is False
    assert [jcs(value) for value in (base, ours, theirs)] == before
    return result


def test_nested_disjoint_edits_and_additions_keep_both_sides():
    base = {'title': 'Before', 'settings': {'enabled': False, 'limit': 10}, 'stable': None}
    ours = {'title': 'Ours', 'settings': {'enabled': True, 'limit': 10}, 'stable': None, 'ours': 0}
    theirs = {'title': 'Before', 'settings': {'enabled': False, 'limit': 20}, 'stable': None, 'theirs': ''}
    assert_value(base, ours, theirs, {'title': 'Ours', 'settings': {'enabled': True, 'limit': 20},
        'stable': None, 'ours': 0, 'theirs': ''})


@pytest.mark.parametrize('target', [None, False, 0, '', 'null', {'new': None}, [3, 2, 1]])
def test_identical_target_changes_do_not_conflict(target):
    assert_value({'field': 'old'}, {'field': target}, {'field': deepcopy(target)}, {'field': target})


@pytest.mark.parametrize('ours_changed', [False, True])
def test_only_changed_side_is_taken_including_a_type_change(ours_changed):
    base = {'field': 'old', 'unchanged': []}
    changed = {'field': {'deep': {'number': 2}}, 'unchanged': []}
    ours, theirs = (changed, base) if ours_changed else (base, changed)
    assert_value(base, ours, theirs, changed)


def test_independent_additions_inside_same_new_object_are_recursive():
    assert_value({}, {'options': {'left': 1}}, {'options': {'right': 2}},
                 {'options': {'left': 1, 'right': 2}})


def test_deletions_preserve_disjoint_edits_and_do_not_create_null_fields():
    assert_value({'old': None, 'other': 1}, {'other': 1}, {'old': None, 'other': 2}, {'other': 2})
    assert_value({'old': None}, {}, {}, {})
    assert_value({'old': 1, 'keep': 2}, {'keep': 2}, {'old': 1}, {})


def test_equivalent_json_numbers_and_object_order_are_not_conflicts():
    assert_value({'n': 0, 'obj': {}}, {'n': 1, 'obj': {'b': 2, 'a': 1}},
                 {'obj': {'a': 1.0, 'b': 2.0}, 'n': 1.0}, {'n': 1, 'obj': {'a': 1, 'b': 2}})
    assert_value({'n': 1}, {'n': 0}, {'n': -0.0}, {'n': 0})


def test_conflicts_keep_exact_three_observations_and_block_target_access():
    result = merge_fields({'a/b~': 'base'}, {'a/b~': 'left'}, {'a/b~': 'right'})
    assert result.merged is False
    assert len(result.conflicts) == 1
    conflict = result.conflicts[0]
    assert conflict.pointer == '/a~1b~0'
    assert [item.present for item in (conflict.base, conflict.ours, conflict.theirs)] == [True] * 3
    assert [item.value for item in (conflict.base, conflict.ours, conflict.theirs)] == ['base', 'left', 'right']
    with pytest.raises(ModelError) as caught:
        _ = result.value
    assert caught.value.reason == 'unresolved_field_merge'
    assert not result.ready and not result.write_authorized


def test_missing_and_null_conflict_observations_are_different():
    result = merge_fields({'x': 1}, {}, {'x': None})
    conflict, = result.conflicts
    assert conflict.base.present and conflict.base.value == 1
    assert conflict.ours.present is False
    assert conflict.theirs.present and conflict.theirs.value is None
    with pytest.raises(ModelError) as caught:
        _ = conflict.ours.value
    assert caught.value.reason == 'merge_field_missing'


def test_array_order_is_preserved_without_a_guessed_set_union():
    assert_value({'steps': [1, 2]}, {'steps': [2, 1]}, {'steps': [1, 2]}, {'steps': [2, 1]})
    result = merge_fields({'steps': [1]}, {'steps': [1, 2]}, {'steps': [1, 3]})
    conflict, = result.conflicts
    assert conflict.pointer == '/steps' and conflict.kind == 'collection_semantics_required'
    assert conflict.ours.value == [1, 2] and conflict.theirs.value == [1, 3]
    with pytest.raises(ModelError):
        _ = result.value


def test_returned_values_are_owned_and_result_has_no_implicit_write_authority():
    base, ours, theirs = {'a': []}, {'a': [{'x': 1}]}, {'a': []}
    result = assert_value(base, ours, theirs, {'a': [{'x': 1}]})
    ours['a'][0]['x'] = 99
    detached = result.value; detached['a'].clear()
    assert result.value == {'a': [{'x': 1}]}
    with pytest.raises(TypeError):
        bool(result)
    with pytest.raises(FrozenInstanceError):
        result.conflicts = ()
    conflict, = merge_fields({}, {'x': {'v': 1}}, {'x': None}).conflicts
    detached = conflict.ours.value; detached['v'] = 99
    assert conflict.ours.value == {'v': 1}
    with pytest.raises(TypeError):
        bool(conflict.ours)


def test_qualified_resource_values_can_be_merged_without_approving_the_inventory(tmp_path):
    original = project(tmp_path/'seed').raw
    path = next(name for name in original if name.startswith('spec/requirements/'))
    record = json.loads(original[path]); variants = []
    for changes in ({}, {'title': 'Our title'}, {'statement': 'The system shall keep both changes.'}):
        files = dict(original); files[path] = jcs({**record, **changes}); variants.append(files)
    sources = bind_files(tmp_path, variants)
    before = inventory(tmp_path)
    with read_only_sources():
        plan = build_merge_inventory(sources, plan_id=PLAN_ID)
        values = [json.loads(getattr(sources, role).files[path]) for role in ROLES]
        # This field engine is downstream of the three qualified native inputs.
        # Metadata/history/identity and full-target acceptance are later gates.
        result = merge_fields(*values)
    expected = {**record, 'title': 'Our title', 'statement': 'The system shall keep both changes.'}
    assert jcs(result.value) == jcs(expected) and result.conflicts == ()
    row = row_for(plan.data, 'artifact', record['id'])
    assert row['target_classification'] == 'conflict'
    assert row['pending_reasons'] == ['semantic_planning_required']
    assert plan.ready is False and result.ready is False
    assert inventory(tmp_path) == before
