"""Explicit missing policy and bounded nested view records in one snapshot."""
from hashlib import sha256
import json

import pytest

from specroad.changes import TargetModel
from specroad.documents import ViewError, resolve_view
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.srx.errors import SrxError
from specroad.validation import ModelDocument
from support.read_only import no_write_attempts
from support.records import ref
from support.relations import edge
from support.srx import binary, expression_document, field, literal
from support.targets import model
from test_document_views import view_project, row_for, aid
from test_document_view_variants import variant_project


def field_column(pointer='/title', kind='string', missing='error'):
    return {'source': {'kind': 'artifact_field', 'pointer': pointer}, 'heading': 'Value',
            'data_type': kind, 'format': 'plain', 'missing': missing}


def relation_column(name):
    return {'source': {'kind': 'relation_projection', 'projection_id': name}, 'heading': name,
            'data_type': 'array', 'format': 'plain', 'missing': 'error'}


def nested_view(view):
    view['columns'] = [field_column(), relation_column('outer')]
    view['grouping'] = []
    view['relation_projections'] = [
        {'id': 'outer', 'direction': 'outgoing', 'types': ['depends_on'], 'max_depth': 1,
         'aggregation': 'records', 'columns': [field_column(), relation_column('leaf')]},
        {'id': 'leaf', 'direction': 'outgoing', 'types': ['depends_on'], 'max_depth': 1,
         'aggregation': 'records', 'columns': [field_column()]}]


def nested_project():
    values = view_project(); nested_view(values[-1]); return values


def only_first(view):
    view['filter'] = expression_document(binary('eq', field('/id'), literal(aid(number=1))))


def resolve(values):
    supplied = model(values); before = supplied.source_files
    with no_write_attempts(): resolved = resolve_view(supplied, ref('VIEW'))
    assert supplied.source_files == before
    return resolved


@pytest.mark.parametrize(('present', 'kind'), [(None, 'null'), (False, 'boolean'), (0, 'number'),
    ('', 'string'), ([], 'array'), ({}, 'object')])
def test_preserve_distinguishes_absence_from_every_present_json_value(present, kind):
    values = view_project()
    for artifact in values[:4]: artifact['extensions'] = {'org.example': {'value': present}}
    del values[0]['extensions']['org.example']['value']
    values[-1]['columns'][0] = field_column('/extensions/org.example/value', kind, 'preserve')
    data = resolve(values).data
    assert row_for(data)['cells'][0] == {'type': 'missing'}
    assert all(row_for(data, n)['cells'][0] == {'type': kind, 'value': present} for n in (2, 3, 4))


@pytest.mark.parametrize(('present', 'kind'), [(None, 'string'), (False, 'number'), (0, 'boolean'), ({}, 'array')])
def test_preserve_does_not_relax_the_declared_type_for_present_values(present, kind):
    values = view_project(); values[0]['extensions'] = {'org.example': {'value': present}}
    values[-1]['columns'][0] = field_column('/extensions/org.example/value', kind, 'preserve')
    with pytest.raises(ViewError) as caught: resolve(values)
    assert caught.value.reason == 'view_column_value_type' and caught.value.pointer == '/columns/0'


@pytest.mark.parametrize('direction', ['asc', 'desc'])
@pytest.mark.parametrize('kind', ['null', 'string'])
def test_missing_groups_are_separate_from_null_and_nfc_string_groups(direction, kind):
    values = view_project()
    for artifact, text in zip(values[1:4], ('é', 'e\u0301', 'z')):
        artifact['extensions'] = {'org.example': {'value': None if kind == 'null' else text}}
    values[-1]['columns'] = [field_column('/extensions/org.example/value', kind, 'preserve')]
    values[-1]['grouping'] = [{'column': 0, 'direction': direction}]
    data = resolve(values).data
    expected = [{'keys': [{'type': 'missing'}], 'artifact_ids': [aid(number=1)]}]
    if kind == 'null':
        expected.append({'keys': [{'type': 'null', 'value': None}], 'artifact_ids': [aid(number=n) for n in (4, 2, 3)]})
    else:
        expected.extend([{'keys': [{'type': 'string', 'value': 'z'}], 'artifact_ids': [aid(number=4)]},
                         {'keys': [{'type': 'string', 'value': 'é'}], 'artifact_ids': [aid(number=n) for n in (2, 3)]}])
    assert data['groups'] == (expected if direction == 'asc' else expected[::-1])
    if kind == 'string': assert row_for(data, 3)['cells'][0]['value'] == 'e\u0301'


def test_nested_records_bind_original_target_bytes_types_revisions_and_declared_cells():
    values = nested_project(); resolved = resolve(values); data = resolved.data
    outer = row_for(data)['cells'][1]['value']
    assert len(outer) == 1 and outer == row_for(data)['relation_projections']['outer']
    middle = outer[0]; last = middle['cells'][1]['value'][0]
    supplied = model(values)
    for row, number in ((middle, 2), (last, 3)):
        raw = next(d.content for d in supplied.documents if json.loads(d.content)['id'] == aid(number=number))
        assert set(row) == {'artifact_id', 'artifact_type', 'revision', 'source_sha256', 'record_sha256', 'cells'}
        assert row['artifact_id'] == aid(number=number) and row['artifact_type'] == 'requirement'
        assert row['revision'] == values[number - 1]['revision']
        assert row['source_sha256'] == sha256(raw).hexdigest()
        assert row['record_sha256'] == canonical_json_sha256(json.loads(raw))
        assert row['cells'][0] == {'type': 'string', 'value': values[number - 1]['title']}
    detached = resolved.data; row_for(detached)['cells'][1]['value'][0]['cells'].clear()
    assert resolved.data == data
    assert not any(data[key] for key in ('project_files_verified', 'full_validation_passed',
        'rendering_performed', 'write_authorized', 'approval_granted'))


@pytest.mark.parametrize(('direction', 'numbers'), [('outgoing', [2]), ('incoming', [3]), ('both', [2, 3])])
@pytest.mark.parametrize('depth', [0, 1, 2, 1000])
def test_each_nested_projection_keeps_its_own_direction_depth_and_distinct_targets(direction, numbers, depth):
    values = nested_project(); outer, leaf = values[-1]['relation_projections']
    outer.update(direction=direction, max_depth=depth)
    leaf.update(types=['conflicts_with'], direction='both', max_depth=1)
    data = resolve(values).data; records = row_for(data)['relation_projections']['outer']
    expected = [] if depth == 0 else numbers if depth == 1 else [2, 3]
    assert [row['artifact_id'] for row in records] == [aid(number=n) for n in expected]
    assert all(row['cells'][1] == {'type': 'array', 'value': []} for row in records)
    assert [row['artifact_id'] for row in row_for(data)['relation_projections']['leaf']] == [aid(number=4)]


@pytest.mark.parametrize('rotation', range(5))
def test_nested_rows_are_stably_ordered_with_shared_children_and_multiple_paths(rotation):
    values = nested_project(); values[0]['relations'].append(edge('depends_on', aid(number=3), number=5))
    values[-1]['relation_projections'][0]['max_depth'] = 2
    expected = resolve(values).data
    assert resolve(values[rotation:] + values[:rotation]).data == expected
    assert [row['artifact_id'] for row in row_for(expected)['relation_projections']['outer']] == [aid(number=2), aid(number=3)]


@pytest.mark.parametrize('platform', ['linux', 'windows'])
def test_nested_relations_share_the_native_configured_graph_even_for_filtered_out_rows(platform):
    values = variant_project(platform); nested_view(values[-2]); only_first(values[-2])
    data = resolve(values).data; projected = row_for(data)['relation_projections']['outer']
    assert data['row_count'] == 1 and data['query_binding']['configuration_binding']['configuration_id'] == ref('CFG')
    if platform == 'linux': assert projected == []
    else:
        assert projected[0]['artifact_id'] == aid(number=2)
        assert projected[0]['cells'][1]['value'][0]['artifact_id'] == aid(number=3)


@pytest.mark.parametrize('missing', ['error', 'preserve'])
def test_nested_columns_apply_their_own_missing_policy_and_error_pointer(missing):
    values = nested_project(); only_first(values[-1])
    values[-1]['relation_projections'][0]['columns'][0] = field_column('/extensions/org.example/value', 'string', missing)
    if missing == 'error':
        with pytest.raises(ViewError) as caught: resolve(values)
        assert caught.value.reason == 'view_column_value_missing'
        assert caught.value.pointer == '/relation_projections/0/columns/0'
    else:
        assert row_for(resolve(values).data)['relation_projections']['outer'][0]['cells'][0] == {'type': 'missing'}


@pytest.mark.parametrize('empty', [False, True])
@pytest.mark.parametrize('case', ['self_cycle', 'mutual_cycle', 'unknown', 'empty_columns', 'object_columns',
    'extra_column', 'dynamic', 'bad_missing', 'bad_type', 'unbounded', 'wildcard', 'negative', 'foreign', 'ids_columns'])
def test_invalid_nested_definitions_fail_before_selection_including_unused_definitions(case, empty):
    values = nested_project(); view = values[-1]; outer, leaf = view['relation_projections']
    view['columns'] = [field_column()]
    if empty: view['filter'] = expression_document(literal(False))
    if case == 'self_cycle': leaf['columns'] = [relation_column('leaf')]
    elif case == 'mutual_cycle': leaf['columns'] = [relation_column('outer')]
    elif case == 'unknown': leaf['columns'] = [relation_column('absent')]
    elif case == 'empty_columns': leaf['columns'] = []
    elif case == 'object_columns': leaf['columns'] = {}
    elif case == 'extra_column': leaf['columns'][0]['execute'] = 'run()'
    elif case == 'dynamic': leaf['columns'][0]['source'] = {'kind': 'callback', 'name': 'run'}
    elif case == 'bad_missing': leaf['columns'][0]['missing'] = 'invent_default'
    elif case == 'bad_type': outer['columns'][1]['data_type'] = 'number'
    elif case == 'unbounded': del leaf['max_depth']
    elif case == 'wildcard': leaf['types'] = ['*']
    elif case == 'negative': leaf['max_depth'] = -1
    elif case == 'foreign': leaf['url'] = 'https://invalid.example/load'
    else: leaf['aggregation'] = 'ids'
    supplied = model(values); before = supplied.source_files
    with no_write_attempts(), pytest.raises((ModelError, SrxError)) as caught: resolve_view(supplied, ref('VIEW'))
    if case in ('self_cycle', 'mutual_cycle'):
        assert caught.value.reason == 'view_relation_projection_cycle'
        assert caught.value.pointer.endswith('/source/projection_id')
    assert supplied.source_files == before


def test_nested_source_byte_changes_rebind_target_without_changing_canonical_value():
    supplied = model(nested_project()); first = resolve_view(supplied, ref('VIEW')).data
    original = next(d for d in supplied.documents if json.loads(d.content)['id'] == aid(number=2))
    raw = (json.dumps(json.loads(original.content), indent=3) + '\n').encode()
    changed = TargetModel(supplied.configuration_bytes, supplied.binding,
        [ModelDocument(d.path, raw if d.path == original.path else d.content) for d in supplied.documents],
        profile=supplied.profile, resource_files=supplied.resource_files)
    with no_write_attempts(): second = resolve_view(changed, ref('VIEW')).data
    before = row_for(first)['relation_projections']['outer'][0]
    after = row_for(second)['relation_projections']['outer'][0]
    assert after['source_sha256'] == sha256(raw).hexdigest() != before['source_sha256']
    assert after['record_sha256'] == before['record_sha256'] and after['cells'] == before['cells']
    assert first['model_root_sha256'] == second['model_root_sha256']
    assert first['input_sha256'] != second['input_sha256']


def test_long_acyclic_projection_chain_keeps_all_declared_levels_without_truncation():
    values = nested_project(); view = values[-1]; only_first(view)
    view['relation_projections'] = []
    for i in range(40):
        columns = [field_column()] if i == 39 else [relation_column('p' + str(i + 1))]
        view['relation_projections'].append({'id': 'p' + str(i), 'direction': 'outgoing',
            'types': ['depends_on'], 'max_depth': 1, 'aggregation': 'records', 'columns': columns})
    view['columns'] = [relation_column('p0')]
    cell = row_for(resolve(values).data)['cells'][0]
    for i in range(40):
        assert cell['type'] == 'array' and len(cell['value']) == 1
        row = cell['value'][0]; assert row['artifact_id'] == aid(number=(i + 1) % 3 + 1)
        cell = row['cells'][0]
    assert cell == {'type': 'string', 'value': 'Beta'}
