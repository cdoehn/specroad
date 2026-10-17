"""Native snapshot view values, bounded relations and typed grouping contracts."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256

import pytest

from specroad.documents import ViewData, ViewError, resolve_view
from specroad.graph.relations import SourceRelations
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.query import NormalizedQuery, query_records
from specroad.srx.errors import SrxError
from support.domain import domain_value
from support.read_only import no_write_attempts
from support.records import record_value, ref
from support.relations import aid, edge
from support.srx import binary, expression_document, field, literal
from support.targets import model, SCOPE


def view_project():
    values = [domain_value('requirement', id=aid(number=n), title=title, revision=revision, owner=owner)
        for n, title, revision, owner in ((1, 'Alpha', 1, 'team'), (2, 'Beta', 3, 'team'),
                                         (3, 'Gamma', 2, 'other'), (4, 'Delta', 4, 'team'))]
    for i, target in enumerate((2, 3, 1)):
        values[i]['relations'] = [edge('depends_on', aid(number=target), number=i + 1)]
    values[0]['relations'].append(edge('conflicts_with', aid(number=4), number=4))
    columns = [{'source': {'kind': 'artifact_field', 'pointer': pointer}, 'heading': heading,
                'data_type': 'string', 'format': 'plain', 'missing': 'error'}
               for pointer, heading in (('/title', 'Title'), ('/owner', 'Owner'))]
    columns += [{'source': {'kind': 'relation_projection', 'projection_id': aggregation},
                 'heading': aggregation, 'data_type': kind, 'format': 'plain', 'missing': 'error'}
                for aggregation, kind in (('ids', 'array'), ('count', 'number'))]
    view = record_value('view', scope_descriptor=deepcopy(SCOPE),
        filter=expression_document(binary('eq', field('/artifact_type'), literal('requirement'))),
        columns=columns, sort=[{'key': 'revision', 'direction': 'desc'}],
        grouping=[{'column': 1, 'direction': 'asc'}], relation_projections=[
            {'id': aggregation, 'direction': 'outgoing', 'types': ['depends_on'],
             'max_depth': 2, 'aggregation': aggregation} for aggregation in ('ids', 'count')])
    return [*values, view]


def row_for(data, n=1):
    return next(row for row in data['rows'] if row['artifact_id'] == aid(number=n))


def test_view_projects_native_query_rows_relations_groups_and_exact_snapshot_bindings():
    supplied = model(view_project()); before = supplied.source_files
    with no_write_attempts(): resolved = resolve_view(supplied, ref('VIEW'))
    data = resolved.data
    assert [row['artifact_id'] for row in data['rows']] == [aid(number=n) for n in (4, 2, 3, 1)]
    assert row_for(data)['cells'] == [{'type': 'string', 'value': 'Alpha'},
        {'type': 'string', 'value': 'team'}, {'type': 'array', 'value': [aid(number=2), aid(number=3)]},
        {'type': 'number', 'value': 2}]
    assert row_for(data, 4)['relation_projections'] == {'ids': [], 'count': 0}
    assert data['groups'] == [
        {'keys': [{'type': 'string', 'value': 'other'}], 'artifact_ids': [aid(number=3)]},
        {'keys': [{'type': 'string', 'value': 'team'}], 'artifact_ids': [aid(number=n) for n in (4, 2, 1)]}]
    records = [SourceRelations(d.content, path=d.path) for d in supplied.documents]
    page = query_records(records, NormalizedQuery.from_data(data['query_binding']['query']),
                         project=supplied.configuration.data)
    assert data['query_result'] == page.data
    assert data['query_binding']['inputs_sha256'] == page.inputs_sha256
    assert data['query_binding']['query_sha256'] == page.query_sha256
    assert data['view']['scope_descriptor'] == data['scope_descriptor'] == SCOPE
    assert data['model_root_sha256'] == supplied.manifest(supplied.artifacts, SCOPE).sha256
    assert data['input_sha256'] == supplied._sources_sha256
    by_id = {r.identity.id: r for r in records}
    assert resolved.view_source_bytes == by_id[ref('VIEW')].source_bytes
    for row in data['rows']:
        record = by_id[row['artifact_id']]
        assert row['source_sha256'] == sha256(record.source_bytes).hexdigest()
        assert row['record_sha256'] == canonical_json_sha256(record.data)
        assert row['revision'] == record.data['revision']
    assert supplied.source_files == before


@pytest.mark.parametrize(('depth', 'targets'), [(0, []), (1, [2]), (2, [2, 3]), (1000, [2, 3])])
def test_depth_limits_are_exact_and_cycles_never_count_the_source(depth, targets):
    values = view_project()
    for projection in values[-1]['relation_projections']: projection['max_depth'] = depth
    data = resolve_view(model(values), ref('VIEW')).data
    assert row_for(data)['relation_projections'] == {'ids': [aid(number=n) for n in targets], 'count': len(targets)}


@pytest.mark.parametrize(('direction', 'targets'), [('outgoing', [2]), ('incoming', [3]), ('both', [2, 3])])
def test_relation_direction_is_evaluated_from_the_actual_stored_edges(direction, targets):
    values = view_project()
    for projection in values[-1]['relation_projections']:
        projection.update(direction=direction, max_depth=1)
    data = resolve_view(model(values), ref('VIEW')).data
    assert row_for(data)['relation_projections'] == {'ids': [aid(number=n) for n in targets], 'count': len(targets)}


def test_multiple_paths_and_inverse_views_do_not_duplicate_related_ids():
    values = view_project(); values[0]['relations'].append(edge('depends_on', aid(number=3), number=5))
    for projection in values[-1]['relation_projections']: projection['direction'] = 'both'
    data = resolve_view(model(values), ref('VIEW')).data
    assert row_for(data)['relation_projections'] == {'ids': [aid(number=2), aid(number=3)], 'count': 2}


def test_row_filter_does_not_redefine_the_bound_projection_graph():
    values = view_project(); view = values[-1]
    view['filter']['expression'] = {'op': 'and', 'args': [view['filter']['expression'],
        binary('eq', field('/owner'), literal('team'))]}
    data = resolve_view(model(values), ref('VIEW')).data
    assert [row['artifact_id'] for row in data['rows']] == [aid(number=n) for n in (4, 2, 1)]
    assert row_for(data)['relation_projections']['ids'] == [aid(number=2), aid(number=3)]


@pytest.mark.parametrize('rotation', range(5))
def test_reordered_inventory_preserves_values_sorting_grouping_and_bindings(rotation):
    values = view_project(); expected = resolve_view(model(values), ref('VIEW')).data
    assert resolve_view(model(values[rotation:] + values[:rotation]), ref('VIEW')).data == expected


@pytest.mark.parametrize('direction', ['asc', 'desc'])
def test_grouping_uses_nfc_utf8_keys_without_rewriting_original_cells(direction):
    values = view_project(); names = ['ä', 'a\u0308', 'z', 'a']
    for artifact, owner in zip(values, names): artifact['owner'] = owner
    values[-1]['grouping'][0]['direction'] = direction
    data = resolve_view(model(values), ref('VIEW')).data
    assert [group['keys'][0]['value'] for group in data['groups']] == (['a', 'z', 'ä'] if direction == 'asc' else ['ä', 'z', 'a'])
    group = next(group for group in data['groups'] if group['keys'][0]['value'] == 'ä')
    assert group['artifact_ids'] == [aid(number=2), aid(number=1)]
    assert row_for(data, 2)['cells'][1]['value'] == 'a\u0308'


def test_new_snapshot_changes_projection_values_and_root_without_mutating_old_data():
    values = view_project(); first = resolve_view(model(values), ref('VIEW')); expected = first.data
    values[1]['relations'] = []; values[1]['revision'] += 1
    second = resolve_view(model(values), ref('VIEW'))
    assert row_for(second.data)['relation_projections'] == {'ids': [aid(number=2)], 'count': 1}
    assert first.view_source_bytes == second.view_source_bytes
    assert first.data == expected and first.sha256 != second.sha256
    assert first.data['input_sha256'] != second.data['input_sha256']
    assert first.data['model_root_sha256'] != second.data['model_root_sha256']


def test_result_is_owned_and_never_grants_rendering_validation_or_write_authority():
    resolved = resolve_view(model(view_project()), ref('VIEW')); expected = resolved.data
    changed = resolved.data; changed['rows'].clear(); changed['groups'].clear(); changed['query_binding'].clear()
    assert resolved.data == expected and resolved.sha256 == canonical_json_sha256(expected)
    assert not any(expected[key] for key in ('project_files_verified', 'full_validation_passed',
        'rendering_performed', 'write_authorized', 'approval_granted'))
    with pytest.raises(FrozenInstanceError): resolved.view_source_bytes = b'{}'
    with pytest.raises(TypeError): bool(resolved)
    with pytest.raises(TypeError): ViewData()


def test_view_has_no_implicit_hundred_row_cap():
    values = view_project(); view = values[-1]; view['relation_projections'] = []; view['columns'] = view['columns'][:2]
    values = [domain_value('requirement', id=aid(number=n), owner='team') for n in range(1, 106)] + [view]
    data = resolve_view(model(values), ref('VIEW')).data
    assert data['row_count'] == data['query_result']['total'] == data['query_result']['returned'] == 105
    assert data['query_result']['truncated'] is False
    assert len(data['groups'][0]['artifact_ids']) == 105


@pytest.mark.parametrize(('case', 'reason'), [
    ('projection_extra', 'view_relation_projection_contract'),
    ('unknown_projection', 'view_relation_projection_missing'),
    ('projection_type', 'view_column_data_type'), ('group_array', 'view_grouping_scalar_required'),
    ('column_template', 'view_column_contract'), ('format', 'view_column_format_provider_required'),
    ('computed', 'view_column_source_provider_required'), ('root', 'view_column_field_required'),
    ('missing_policy', 'view_column_missing_provider_required'),
    ('configuration', 'view_configuration_provider_required')])
def test_unsupported_declarations_fail_even_when_the_filter_selects_no_rows(case, reason):
    values = view_project(); view = values[-1]; view['filter'] = expression_document(literal(False))
    if case == 'projection_extra': view['relation_projections'][0]['loader'] = 'external.function'
    elif case == 'unknown_projection': view['columns'][2]['source']['projection_id'] = 'unknown'
    elif case == 'projection_type': view['columns'][2]['data_type'] = 'number'
    elif case == 'group_array': view['grouping'][0]['column'] = 2
    elif case == 'column_template': view['columns'][0]['template'] = '{{ run() }}'
    elif case == 'format': view['columns'][0]['format'] = 'external.function'
    elif case == 'computed': view['columns'][0]['source'] = {'kind': 'computed_status', 'name': 'verification_result'}
    elif case == 'root': view['columns'][0]['source']['pointer'] = ''
    elif case == 'configuration': view['scope_descriptor']['configuration_id'] = ref('CFG')
    else: view['columns'][0]['missing'] = 'invent_default'
    supplied = model(values); before = supplied.source_files
    with no_write_attempts(), pytest.raises(ViewError) as caught: resolve_view(supplied, ref('VIEW'))
    assert caught.value.reason == reason and supplied.source_files == before


@pytest.mark.parametrize('case', ['missing', 'wrong_type', 'script_filter', 'negative_depth', 'missing_target'])
def test_unresolved_sources_and_invalid_filter_or_graph_never_produce_view_data(case):
    values = view_project(); view_id = ref('VIEW')
    if case == 'missing': values.pop()
    elif case == 'wrong_type': view_id = aid(number=1)
    elif case == 'script_filter': values[-1]['filter']['expression'] = {'op': 'execute', 'script': 'run()'}
    elif case == 'negative_depth': values[-1]['relation_projections'][0]['max_depth'] = -1
    else: values[0]['relations'][0]['target'] = aid(number=99)
    supplied = model(values); before = supplied.source_files
    with no_write_attempts(), pytest.raises((ModelError, SrxError)): resolve_view(supplied, view_id)
    assert supplied.source_files == before
