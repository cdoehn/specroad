"""Snapshot identity, native query rows and typed literal table contracts."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.documents import TableBlockData, TableBlockError, resolve_table_block
from specroad.graph.relations import SourceRelations
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.query import NormalizedQuery, query_records
from specroad.srx.errors import SrxError
from support.domain import domain_value
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import block_value, record_value, ref
from support.relations import aid
from support.srx import binary, expression_document, field, literal
from support.targets import model, SCOPE


def table_project(branch='embedded', *, limit=10):
    artifacts = [domain_value('requirement', id=aid(number=n), title=title, revision=revision, owner=owner)
        for n, title, revision, owner in ((1, 'Alpha', 1, 'team'), (2, 'Beta', 3, 'team'), (3, 'Gamma', 2, 'other'))]
    predicate = expression_document({'op': 'and', 'args': [
        binary('eq', field('/artifact_type'), literal('requirement')),
        binary('eq', field('/owner'), literal('team'))]})
    block = block_value('query' if branch != 'table_view' else 'table')
    if branch == 'embedded':
        query = NormalizedQuery(filters={'type': ['requirement']}, srx_filters=[predicate],
                                sort=['revision:desc'], limit=limit)
        block['payload'] = {'query': query.data, 'columns': [{'field': '/title'}, {'field': '/revision'}],
                            'empty_policy': 'omit'}
        block['relations'] = []
    else:
        view = record_value('view', scope_descriptor=deepcopy(SCOPE), filter=predicate,
            columns=[{'source': {'kind': 'artifact_field', 'pointer': pointer}, 'heading': heading,
                      'data_type': kind, 'format': 'plain', 'missing': 'error'}
                     for pointer, heading, kind in (('/title', 'Title', 'string'), ('/revision', 'Revision', 'number'))],
            sort=[{'key': 'revision', 'direction': 'desc'}])
        if branch == 'table_view':
            block['payload'] = {'source': 'view'}
            block['relations'] = block_value('query')['relations']
        else: block['payload']['columns'] = [{'field': '/title'}, {'field': '/revision'}]
        artifacts.append(view)
    return [block, *artifacts]


@pytest.mark.parametrize('branch', ['embedded', 'query_view', 'table_view'])
def test_queries_and_basic_views_produce_the_same_bound_typed_rows(branch):
    supplied = model(table_project(branch))
    with no_write_attempts(): resolved = resolve_table_block(supplied, ref('BLOCK'))
    data = resolved.data
    assert [row['artifact_id'] for row in data['rows']] == [aid(number=2), aid(number=1)]
    assert [row['cells'] for row in data['rows']] == [
        [{'type': 'string', 'value': 'Beta'}, {'type': 'number', 'value': 3}],
        [{'type': 'string', 'value': 'Alpha'}, {'type': 'number', 'value': 1}]]
    assert data['row_count'] == 2 and data['outcome'] == 'rows'
    assert data['row_source'] == ('query' if branch == 'embedded' else 'view')
    assert data['project_id'] == supplied.binding.project_id and data['scope_descriptor'] == SCOPE
    assert data['model_root_sha256'] == supplied.manifest(supplied.artifacts, SCOPE).sha256
    assert data['input_sha256'] == supplied._sources_sha256
    query = NormalizedQuery.from_data(data['query_binding']['query'])
    records = [SourceRelations(d.content, path=d.path) for d in supplied.documents]
    native = query_records(records, query, project=supplied.configuration.data)
    assert data['query_result'] == native.data and data['query_binding']['query_sha256'] == native.query_sha256
    assert data['query_binding']['inputs_sha256'] == native.inputs_sha256
    by_id = {r.identity.id: r for r in records}
    assert resolved.block_source_bytes == by_id[ref('BLOCK')].source_bytes
    for row in data['rows']:
        assert row['source_sha256'] == sha256(by_id[row['artifact_id']].source_bytes).hexdigest()
        assert row['record_sha256'] == canonical_json_sha256(by_id[row['artifact_id']].data)
        assert row['revision'] == by_id[row['artifact_id']].data['revision']
    if branch != 'embedded':
        assert resolved.view_source_bytes == by_id[ref('VIEW')].source_bytes
        assert data['view']['scope_descriptor'] == SCOPE
        assert data['view']['reference_pointer'] == '/relations/0'
    else: assert resolved.view_source_bytes is None and data['view'] is None


def test_embedded_query_retains_exact_filter_sort_offset_limit_and_full_total():
    values = table_project(limit=1); query = values[0]['payload']['query']; query['offset'] = 1
    data = resolve_table_block(model(values), ref('BLOCK')).data
    assert [row['artifact_id'] for row in data['rows']] == [aid(number=1)]
    assert {k: v for k, v in data['query_result'].items() if k != 'items'} == {
        'total': 2, 'returned': 1, 'offset': 1, 'limit': 1, 'truncated': False}
    assert data['query_binding']['query'] == query


def test_table_columns_are_an_explicit_projection_independent_of_native_query_select():
    values = table_project(); values[0]['payload']['query']['select'] = ['/id']
    data = resolve_table_block(model(values), ref('BLOCK')).data
    assert data['query_result']['items'][0]['values'] == {'/id': aid(number=2)}
    assert data['rows'][0]['cells'] == [{'type': 'string', 'value': 'Beta'}, {'type': 'number', 'value': 3}]


@pytest.mark.parametrize('rotation', range(5))
def test_input_inventory_order_does_not_change_projection_or_snapshot_bindings(rotation):
    values = table_project('table_view'); expected = resolve_table_block(model(values), ref('BLOCK')).data
    rotated = values[rotation:] + values[:rotation]
    assert resolve_table_block(model(rotated), ref('BLOCK')).data == expected


@pytest.mark.parametrize(('value', 'kind'), [(None, 'null'), (False, 'boolean'), (0, 'number'),
    (1.5, 'number'), ('{{ inert text }}', 'string'), ([1, False], 'array'), ({'state': 'missing'}, 'object')])
def test_literal_rows_have_json_types_and_do_not_coerce_values_or_execute_text(value, kind):
    block = block_value('table'); block['payload'] = {'columns': [{'field': 'value', 'data_type': kind}], 'rows': [[value]]}
    with no_write_attempts(): data = resolve_table_block(model([block]), block['id']).data
    assert data['rows'] == [{'cells': [{'type': kind, 'value': value}]}]
    assert data['row_source'] == 'literal' and data['query_binding'] is None and data['query_result'] is None


def test_missing_null_false_and_an_actual_missing_shaped_object_remain_distinct_cells():
    values = table_project(limit=1)
    values[0]['payload']['columns'] = [{'field': '/absent'}, {'field': '/extensions/org.example/null'},
        {'field': '/extensions/org.example/flag'}, {'field': '/extensions/org.example/object'}]
    values[2]['extensions'] = {'org.example': {'null': None, 'flag': False, 'object': {'state': 'missing'}}}
    data = resolve_table_block(model(values), ref('BLOCK')).data
    assert data['rows'][0]['cells'] == [{'type': 'missing'}, {'type': 'null', 'value': None},
        {'type': 'boolean', 'value': False}, {'type': 'object', 'value': {'state': 'missing'}}]


@pytest.mark.parametrize('policy', ['omit', 'message', 'error'])
def test_empty_query_policy_is_semantic_data_or_a_structured_error(policy):
    values = table_project(limit=0); values[0]['payload']['empty_policy'] = policy
    if policy == 'error':
        with no_write_attempts(), pytest.raises(TableBlockError) as caught:
            resolve_table_block(model(values), ref('BLOCK'))
        assert caught.value.reason == 'table_query_empty' and caught.value.pointer == '/payload/empty_policy'
    else:
        with no_write_attempts(): data = resolve_table_block(model(values), ref('BLOCK')).data
        assert data['outcome'] == policy and data['rows'] == [] and data['row_count'] == 0
        assert data['query_result']['total'] == 2 and data['query_result']['truncated'] is True


def test_basic_view_has_no_hidden_one_hundred_row_truncation():
    values = table_project('table_view'); values = [a for a in values if a['artifact_type'] != 'requirement']
    values.extend(domain_value('requirement', id=aid(number=n), owner='team', revision=1)
                  for n in range(1, 106))
    data = resolve_table_block(model(values), ref('BLOCK')).data
    assert data['row_count'] == data['query_result']['returned'] == data['query_result']['total'] == 105
    assert not data['query_result']['truncated']
    assert [row['artifact_id'] for row in data['rows']] == [aid(number=n) for n in range(1, 106)]


def test_view_configuration_is_resolved_from_the_same_snapshot_before_row_selection():
    values = table_project('table_view'); configuration = record_value('configuration')
    values.append(configuration); values[-2]['scope_descriptor']['configuration_id'] = configuration['id']
    values[2]['applicability'] = expression_document(binary('eq',
        field('/effective_values/platform', 'configuration'), literal('windows')))
    data = resolve_table_block(model(values), ref('BLOCK')).data
    assert [row['artifact_id'] for row in data['rows']] == [aid(number=1)]
    assert data['query_binding']['configuration_binding']['configuration_id'] == configuration['id']


def test_new_snapshot_observes_changed_rows_without_changing_the_block_or_old_result():
    values = table_project(); first_model = model(values); first = resolve_table_block(first_model, ref('BLOCK'))
    expected = first.data; changed = deepcopy(values); changed[1].update(title='New Alpha', revision=4)
    second = resolve_table_block(model(changed), ref('BLOCK'))
    assert [row['artifact_id'] for row in second.data['rows']] == [aid(number=1), aid(number=2)]
    assert second.data['rows'][0]['cells'][0] == {'type': 'string', 'value': 'New Alpha'}
    assert second.block_source_bytes == first.block_source_bytes
    assert second.data['input_sha256'] != first.data['input_sha256']
    assert second.data['model_root_sha256'] != first.data['model_root_sha256'] and first.data == expected


def test_data_is_detached_and_never_claims_rendering_whole_project_or_write_approval():
    resolved = resolve_table_block(model(table_project()), ref('BLOCK')); expected = resolved.data
    changed = resolved.data; changed['rows'].clear(); changed['columns'].clear(); changed['query_binding'].clear()
    assert resolved.data == expected and resolved.sha256 == canonical_json_sha256(expected)
    assert expected['validation_scope'] == 'supplied_snapshot_table_projection'
    assert not any(expected[k] for k in ('project_files_verified', 'full_validation_passed',
        'document_structure_checked', 'rendering_performed', 'write_authorized', 'approval_granted'))
    with pytest.raises(FrozenInstanceError): resolved.block_source_bytes = b'{}'
    with pytest.raises(TypeError): bool(resolved)
    with pytest.raises(TypeError): TableBlockData()


def test_projection_reads_owned_bytes_after_external_files_are_removed(tmp_path):
    supplied = model(table_project('table_view')); path = tmp_path / 'source.json'
    path.write_bytes(supplied.documents[0].content); before = inventory(tmp_path)
    with no_write_attempts(): first = resolve_table_block(supplied, ref('BLOCK'))
    assert inventory(tmp_path) == before
    path.unlink()
    with no_write_attempts(): second = resolve_table_block(supplied, ref('BLOCK'))
    assert first.data == second.data and not path.exists()


@pytest.mark.parametrize('failure', ['template_column', 'foreign_query', 'script_filter',
    'missing_view', 'copied_artifact', 'row_width', 'declared_boolean_as_number'])
def test_invalid_or_executable_declarations_never_produce_table_data(failure):
    values = table_project('table_view' if failure == 'missing_view' else 'embedded')
    if failure == 'template_column': values[0]['payload']['columns'][0]['template'] = 'execute()'
    elif failure == 'foreign_query': values[0]['payload']['query']['source'] = 'https://invalid.example/data'
    elif failure == 'script_filter': values[0]['payload']['query']['srx_filters'][0]['expression']['expression'] = {'op': 'execute'}
    elif failure == 'missing_view': values.pop()
    else:
        values = [block_value('table')]
        if failure == 'copied_artifact': values[0]['payload']['rows'] = [[{'wrapped': domain_value('requirement')}]]
        elif failure == 'row_width': values[0]['payload']['rows'] = [[]]
        else:
            values[0]['payload'] = {'columns': [{'field': 'count', 'data_type': 'number'}], 'rows': [[True]]}
    with no_write_attempts(), pytest.raises((ModelError, SrxError)):
        resolve_table_block(model(values), ref('BLOCK'))


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_snapshot_table_projection_runs_with_identical_bindings_in_isolated_core_and_pyz(tmp_path, mode):
    supplied = model(table_project('table_view')); expected = resolve_table_block(supplied, ref('BLOCK')).data
    body = '''import json
from specroad.changes import TargetModel
from specroad.documents import resolve_table_block
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
'''
    body += 'config=' + repr(supplied.configuration_bytes) + '\n'
    body += 'documents=' + repr([(d.path, d.content) for d in supplied.documents]) + '\n'
    body += 'resources=' + repr([(d.path, d.content) for d in supplied.resource_files]) + '\n'
    body += 'core_key=' + repr(supplied.profile.profile_chain[0]) + '\n'
    body += '''profile=compose_profiles([ProfileResource(raw) for path,raw in resources],core_key=core_key)
owned=TargetModel(config,ProjectReadBinding('sample','/explicit/provider',(1,2)),
 [ModelDocument(path,raw) for path,raw in documents],profile=profile,
 resource_files=[ModelDocument(path,raw) for path,raw in resources])
'''
    body += 'print(json.dumps(resolve_table_block(owned,' + repr(ref('BLOCK')) + ').data,sort_keys=True))\n'
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
