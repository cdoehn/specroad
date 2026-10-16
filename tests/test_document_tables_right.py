"""Closed table declarations and original snapshot boundaries, without rendering."""
from copy import deepcopy
from hashlib import sha256
import builtins
import io
import json
import os

import pytest

from specroad.changes import TargetModel
from specroad.documents import TableBlockError, resolve_table_block
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.query import NormalizedQuery
from specroad.srx.errors import SrxError
from specroad.validation import ModelDocument
from support.domain import domain_value
from support.read_only import inventory, no_write_attempts
from support.records import ref
from support.relations import aid
from support.srx import expression_document, literal
from support.targets import model
from test_document_tables import table_project


def rejected(values, *, reason=None, pointer=None):
    supplied = model(values); before = supplied.source_files
    with no_write_attempts(), pytest.raises((ModelError, SrxError)) as caught:
        resolve_table_block(supplied, ref('BLOCK'))
    if reason is not None: assert caught.value.reason == reason
    if pointer is not None: assert caught.value.pointer == pointer
    assert supplied.source_files == before
    return caught.value


@pytest.mark.parametrize('branch', ['embedded', 'query_view', 'table_view'])
@pytest.mark.parametrize('extra', ['template', 'script', 'loader', 'view_id', 'records', 'source_url'])
def test_executable_or_alternative_source_fields_cannot_enter_the_block_payload(branch, extra):
    values = table_project(branch)
    values[0]['payload'][extra] = {'template': 'run()', 'script': 'import os', 'loader': 'external.function',
        'view_id': ref('VIEW'), 'records': [deepcopy(values[1])],
        'source_url': 'https://invalid.example/data'}[extra]
    error = rejected(values)
    assert error.path == artifact_path('content_block', ref('BLOCK'), 'SR')


@pytest.mark.parametrize('branch', ['query_view', 'table_view'])
@pytest.mark.parametrize('failure', ['absent_relation', 'wrong_relation', 'wrong_target_type', 'missing_target', 'different_identity'])
def test_view_binding_requires_one_actual_reference_and_its_exact_stored_target(branch, failure):
    values = table_project(branch)
    if failure == 'absent_relation': values[0]['relations'] = []
    elif failure == 'wrong_relation': values[0]['relations'][0]['type'] = 'derived_from'
    elif failure == 'wrong_target_type': values[0]['relations'][0]['target'] = aid(number=1)
    elif failure == 'missing_target': values.pop()
    else: values[-1]['id'] = ref('VIEW', '1')
    expected = {'absent_relation': 'block_reference_cardinality', 'wrong_relation': 'block_reference_cardinality',
        'wrong_target_type': 'block_reference_type', 'missing_target': 'missing_relation_target',
        'different_identity': 'missing_relation_target'}
    rejected(values, reason=expected[failure])


@pytest.mark.parametrize('branch', ['query_view', 'table_view'])
def test_view_columns_cannot_hide_missing_declarations_behind_query_shorthand(branch):
    values = table_project(branch); values[-1]['columns'] = [{'field': '/title'}]
    error = rejected(values, reason='table_column_contract', pointer='/columns/0')
    assert error.path == artifact_path('view', ref('VIEW'), 'SR')


@pytest.mark.parametrize('case', ['source_kind', 'source_url', 'source_callback', 'column_template',
    'format', 'missing', 'null_type', 'unknown_type', 'empty_heading', 'missing_heading'])
def test_unsupported_view_columns_are_rejected_even_with_an_empty_filter_and_query_override(case):
    values = table_project('query_view'); view = values[-1]
    view['filter'] = expression_document(literal(False)); column = view['columns'][0]
    if case == 'source_kind': column['source']['kind'] = 'python'
    elif case == 'source_url': column['source']['url'] = 'https://invalid.example/data'
    elif case == 'source_callback': column['source']['callback'] = '__import__'
    elif case == 'column_template': column['template'] = '{{ execute() }}'
    elif case == 'format': column['format'] = '{{ execute() }}'
    elif case == 'missing': column['missing'] = 'external.default'
    elif case == 'null_type': column['data_type'] = None
    elif case == 'unknown_type': column['data_type'] = 'python.object'
    elif case == 'empty_heading': column['heading'] = ' '
    else: column.pop('heading')
    error = rejected(values)
    assert isinstance(error, TableBlockError) and error.path == artifact_path('view', ref('VIEW'), 'SR')
    assert error.pointer.startswith('/columns/0')


@pytest.mark.parametrize('pointer', ['https://invalid.example/data', 'file:///tmp/source.json',
    '../source', '/./title', '/../title', '/bad~2escape', 42])
def test_foreign_loaders_and_nonstatic_pointers_are_rejected_before_any_row_selection(pointer):
    values = table_project('table_view'); values[-1]['filter'] = expression_document(literal(False))
    values[-1]['columns'][0]['source']['pointer'] = pointer
    rejected(values, reason='table_column_pointer_invalid', pointer='/columns/0/source/pointer')


@pytest.mark.parametrize('case', ['hash', 'source', 'callback', 'projection', 'offset', 'limit', 'duplicate_projection'])
def test_embedded_query_is_a_closed_native_envelope_even_when_the_page_is_empty(case):
    values = table_project(limit=0); query = values[0]['payload']['query']
    if case == 'hash': query['srx_filters'][0]['sha256'] = '0' * 64
    elif case == 'source': query['source'] = '/tmp/foreign.json'
    elif case == 'callback': query['callback'] = 'os.system'
    elif case == 'projection': query['select'] = ['$.title']
    elif case == 'offset': query['offset'] = True
    elif case == 'limit': query['limit'] = -1
    else: query['select'] = ['/title', '/title']
    rejected(values)


@pytest.mark.parametrize('case', ['partial', 'document', 'foreign_selector', 'missing_configuration',
    'grouping', 'relations', 'executable_sort'])
def test_unsupported_scope_and_projection_providers_are_not_silently_widened(case):
    values = table_project('table_view'); view = values[-1]
    if case == 'partial': view['scope_descriptor']['boundary_policy'] = 'partial'
    elif case == 'document':
        view['scope_descriptor'].update(scope_kind='document', selector={'document_id': ref('DOC')})
    elif case == 'foreign_selector': view['scope_descriptor']['selector'] = {'path': '/tmp/foreign.json'}
    elif case == 'missing_configuration': view['scope_descriptor']['configuration_id'] = ref('CFG')
    elif case == 'grouping': view['grouping'] = [{'key': 'owner'}]
    elif case == 'relations': view['relation_projections'] = [{'callback': 'execute()'}]
    else: view['sort'][0]['callback'] = 'execute()'
    rejected(values)


@pytest.mark.parametrize('pointer', ['/verification_result', '/verification_result/passed'])
def test_missing_computed_column_provider_fails_even_for_an_empty_native_query(pointer):
    values = table_project(limit=0); values[0]['payload']['columns'] = [{'field': pointer}]
    rejected(values, reason='query_verification_provider_required', pointer='/payload/columns/0/field')


@pytest.mark.parametrize(('pointer', 'declared', 'reason'), [
    ('/not_present', 'string', 'table_column_value_missing'),
    ('/revision', 'boolean', 'table_column_value_type'),
    ('/extensions/org.example/flag', 'number', 'table_column_value_type')])
def test_full_view_cell_contracts_reject_missing_values_and_type_coercion(pointer, declared, reason):
    values = table_project('table_view'); values[2]['extensions'] = {'org.example': {'flag': True}}
    values[-1]['columns'] = [{'source': {'kind': 'artifact_field', 'pointer': pointer},
        'heading': 'Value', 'data_type': declared, 'format': 'plain', 'missing': 'error'}]
    rejected(values, reason=reason, pointer='/columns/0')


@pytest.mark.parametrize('selector', [None, True, 0, [], {}, '', ref('BLOCK', '1')])
def test_block_selection_never_falls_back_to_the_first_block(selector):
    supplied = model(table_project())
    with no_write_attempts(), pytest.raises(TableBlockError) as caught:
        resolve_table_block(supplied, selector)
    assert caught.value.reason == ('content_block_not_found' if type(selector) is str else 'content_block_id_required')
    assert caught.value.pointer == '/block_id'


def test_a_foreign_or_modified_model_cannot_reuse_the_snapshot_binding():
    supplied = model(table_project()); documents = list(supplied.documents)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_table_block({'documents': documents}, ref('BLOCK'))
    assert caught.value.reason == 'document_target_model_required'
    documents[0] = ModelDocument(documents[0].path, documents[0].content + b'\n')
    object.__setattr__(supplied, 'documents', tuple(documents))
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_table_block(supplied, ref('BLOCK'))
    assert caught.value.reason == 'target_sources_changed'


@pytest.mark.parametrize('target', ['view', 'row'])
def test_duplicate_source_identity_cannot_select_a_different_view_or_row_copy(target):
    supplied = model(table_project('table_view'))
    original = next(d for d in supplied.documents if json.loads(d.content)['artifact_type'] ==
                    ('view' if target == 'view' else 'requirement'))
    value = json.loads(original.content); value['revision'] += 1
    extra = ModelDocument('artifacts/' + target + '/duplicate.json', json.dumps(value).encode())
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        TargetModel(supplied.configuration_bytes, supplied.binding, [*supplied.documents, extra],
                    profile=supplied.profile, resource_files=supplied.resource_files)
    assert caught.value.reason == 'target_duplicate_artifact_id'


@pytest.mark.parametrize('target', ['block', 'view', 'row'])
def test_byte_only_source_changes_rebind_original_bytes_without_inventing_model_changes(target):
    supplied = model(table_project('table_view')); first = resolve_table_block(supplied, ref('BLOCK'))
    ident = {'block': ref('BLOCK'), 'view': ref('VIEW'), 'row': aid(number=2)}[target]
    document = next(d for d in supplied.documents if json.loads(d.content)['id'] == ident)
    raw = (json.dumps(json.loads(document.content), indent=3) + '\n').encode()
    documents = [ModelDocument(d.path, raw if d.path == document.path else d.content) for d in supplied.documents]
    updated = TargetModel(supplied.configuration_bytes, supplied.binding, documents,
                          profile=supplied.profile, resource_files=supplied.resource_files)
    with no_write_attempts(): second = resolve_table_block(updated, ref('BLOCK'))
    old, new = first.data, second.data
    assert old['model_root_sha256'] == new['model_root_sha256']
    assert old['input_sha256'] != new['input_sha256']
    assert old['query_binding']['query_sha256'] == new['query_binding']['query_sha256']
    assert old['query_binding']['inputs_sha256'] != new['query_binding']['inputs_sha256']
    assert old['query_result'] == new['query_result']
    if target == 'row': before, after = old['rows'][0], new['rows'][0]
    else: before, after = old[target], new[target]
    assert before['revision'] == after['revision'] and before['record_sha256'] == after['record_sha256']
    assert before['source_sha256'] != after['source_sha256'] == sha256(raw).hexdigest()
    if target == 'block': assert second.block_source_bytes == raw
    elif target == 'view': assert second.view_source_bytes == raw
    assert supplied.source_files[document.path] == document.content


def test_a_changed_view_changes_new_rows_without_changing_block_bytes_or_old_results():
    values = table_project('table_view'); first = resolve_table_block(model(values), ref('BLOCK'))
    old = first.data; values[-1]['revision'] += 1
    values[-1]['filter'] = expression_document(literal(False))
    with no_write_attempts(): second = resolve_table_block(model(values), ref('BLOCK'))
    assert second.data['rows'] == [] and second.data['outcome'] == 'empty'
    assert second.data['query_result']['total'] == 0
    assert second.data['view']['revision'] == old['view']['revision'] + 1
    assert second.data['query_binding']['query_sha256'] != old['query_binding']['query_sha256']
    assert second.block_source_bytes == first.block_source_bytes and second.data['block'] == old['block']
    assert first.data == old and len(first.data['rows']) == 2


def test_native_sort_collation_and_ascending_identity_ties_are_preserved_by_table_rows():
    values = table_project(); values = values[:1] + [
        domain_value('requirement', id=aid(number=n), title=title, owner='team')
        for n, title in ((3, 'é'), (1, 'Z'), (2, 'e\u0301'))]
    values[0]['payload']['query'] = NormalizedQuery(filters={'type': ['requirement']}, sort=['title:desc']).data
    with no_write_attempts(): data = resolve_table_block(model(values), ref('BLOCK')).data
    assert [r['artifact_id'] for r in data['rows']] == [aid(number=n) for n in (2, 3, 1)]
    assert [r['cells'][0]['value'] for r in data['rows']] == ['e\u0301', 'é', 'Z']
    assert [r['id'] for r in data['query_result']['items']] == [aid(number=n) for n in (2, 3, 1)]


def test_column_pointer_escapes_and_array_indices_use_native_srx_semantics():
    values = table_project(limit=1)
    values[2]['extensions'] = {'org.example': {'a/b': {'~': ['kept']}}}
    values[0]['payload']['columns'] = [{'field': '/extensions/org.example/a~1b/~0/0'},
                                      {'field': '/extensions/org.example/a~1b/~0/9'}]
    with no_write_attempts(): data = resolve_table_block(model(values), ref('BLOCK')).data
    assert data['rows'][0]['cells'] == [{'type': 'string', 'value': 'kept'}, {'type': 'missing'}]
    values[0]['payload']['columns'][0]['field'] = '/extensions/org.example/a~1b/~0/00'
    rejected(values, reason='invalid_array_index')


@pytest.mark.parametrize('case', ['valid', 'invalid'])
def test_table_resolution_does_not_read_paths_or_execute_data_and_preserves_real_files(tmp_path, monkeypatch, case):
    values = table_project('table_view')
    values[2]['title'] = '{{ run() }} https://invalid.example/data file:///tmp/source.json'
    if case == 'invalid': values[-1]['columns'][0]['source']['loader'] = 'external.function'
    supplied = model(values)
    for name, raw in supplied.source_files.items():
        p = tmp_path / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(raw)
    before = inventory(tmp_path); calls = []
    def forbidden(*args, **kwargs):
        calls.append((args, kwargs)); raise AssertionError('Unexpected source read')
    with no_write_attempts(), monkeypatch.context() as guard:
        for owner in (builtins, io, os): guard.setattr(owner, 'open', forbidden)
        if case == 'invalid':
            with pytest.raises(TableBlockError): resolve_table_block(supplied, ref('BLOCK'))
        else:
            result = resolve_table_block(supplied, ref('BLOCK'))
            assert result.data['rows'][0]['cells'][0] == {'type': 'string', 'value': values[2]['title']}
    assert calls == [] and inventory(tmp_path) == before
    assert supplied.artifacts == model(values).artifacts
