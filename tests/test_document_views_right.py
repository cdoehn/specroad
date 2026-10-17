"""Closed view declarations and exact snapshot boundaries without execution."""
import builtins
from copy import deepcopy
from hashlib import sha256
import io
import json
import os
import socket
import subprocess

import pytest

from specroad.changes import TargetModel
from specroad.documents import ViewError, resolve_view
from specroad.model.errors import ModelError
from specroad.srx.errors import SrxError
from specroad.validation import ModelDocument
from support.model import configuration_value
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import ref
from support.relations import aid, edge
from support.srx import expression_document, literal
from support.targets import model
from test_document_views import view_project, row_for


def bound_view_model(values=None):
    return model(view_project() if values is None else values)


def rejected(values, reason=None, pointer=None):
    supplied = bound_view_model(values); before = supplied.source_files
    with no_write_attempts(), pytest.raises((ModelError, SrxError)) as caught:
        resolve_view(supplied, ref('VIEW'))
    if reason is not None: assert caught.value.reason == reason
    if pointer is not None: assert caught.value.pointer == pointer
    assert supplied.source_files == before
    return caught.value


@pytest.mark.parametrize('empty', [False, True])
@pytest.mark.parametrize('formats', [['external.render'], ['file:///tmp/renderer.py'],
    ['https://invalid.example/render'], ['{{ run() }}'], ['json', 'json']])
def test_only_closed_unique_format_names_are_accepted_before_selection(empty, formats):
    values = view_project(); values[-1]['formats'] = formats
    if empty: values[-1]['filter'] = expression_document(literal(False))
    duplicate = formats == ['json', 'json']
    rejected(values, 'view_format_duplicate' if duplicate else 'view_format_provider_required',
             '/formats/1' if duplicate else '/formats/0')


def test_all_declared_core_formats_are_inert_capabilities_not_render_operations():
    values = view_project(); values[-1]['formats'] = ['json', 'markdown', 'html', 'csv']
    with no_write_attempts(): data = resolve_view(bound_view_model(values), ref('VIEW')).data
    assert data['formats'] == values[-1]['formats'] and data['rendering_performed'] is False
    assert data['row_count'] == 4


@pytest.mark.parametrize('empty', [False, True])
@pytest.mark.parametrize('field', ['template', 'script', 'loader', 'source_url', 'function'])
def test_foreign_column_execution_fields_cannot_hide_behind_an_empty_filter(empty, field):
    values = view_project(); values[-1]['columns'][0][field] = 'external.function'
    if empty: values[-1]['filter'] = expression_document(literal(False))
    rejected(values, 'view_column_contract', '/columns/0')


@pytest.mark.parametrize('pointer', ['https://invalid.example/data', 'file:///tmp/source.json',
    '../source', '/./title', '/../title', '/bad~2escape', 42])
def test_projection_paths_are_static_native_pointers_even_without_rows(pointer):
    values = view_project(); values[-1]['filter'] = expression_document(literal(False))
    values[-1]['columns'][0]['source']['pointer'] = pointer
    rejected(values, 'view_column_pointer_invalid', '/columns/0/source/pointer')


@pytest.mark.parametrize('case', ['missing_direction', 'missing_types', 'missing_depth',
    'missing_aggregation', 'wildcard', 'empty_types', 'duplicate_type', 'unknown_type',
    'boolean_depth', 'negative_depth', 'dynamic_depth', 'callback', 'duplicate_id', 'nested_path'])
def test_relation_declarations_cannot_drop_bounds_or_load_custom_graph_functions(case):
    values = view_project(); view = values[-1]; projection = view['relation_projections'][0]
    view['filter'] = expression_document(literal(False))
    if case.startswith('missing_'):
        projection.pop({'missing_direction': 'direction', 'missing_types': 'types',
                        'missing_depth': 'max_depth', 'missing_aggregation': 'aggregation'}[case])
    elif case == 'wildcard': projection['types'] = '*'
    elif case == 'empty_types': projection['types'] = []
    elif case == 'duplicate_type': projection['types'] = ['depends_on', 'depends_on']
    elif case == 'unknown_type': projection['types'] = ['external.edge']
    elif case == 'boolean_depth': projection['max_depth'] = True
    elif case == 'negative_depth': projection['max_depth'] = -1
    elif case == 'dynamic_depth': projection['max_depth'] = {'function': 'external.limit'}
    elif case == 'callback': projection['aggregation'] = 'external.aggregate'
    elif case == 'duplicate_id': view['relation_projections'][1]['id'] = projection['id']
    else: view['columns'][2]['source']['pointer'] = '/related/../private'
    error = rejected(values)
    assert error.pointer.startswith(('/relation_projections/', '/columns/2'))


@pytest.mark.parametrize('case', ['partial', 'specification', 'explicit', 'foreign_selector'])
def test_scope_declarations_cannot_silently_widen_or_discover_unbound_sources(case):
    values = view_project(); scope = values[-1]['scope_descriptor']
    if case == 'partial': scope['boundary_policy'] = 'partial'
    elif case == 'specification': scope['scope_kind'] = 'specification'
    elif case == 'explicit':
        scope.update(scope_kind='explicit', selector={'artifact_ids': [aid(number=1)], 'resource_ids': []})
    else: scope['selector']['source'] = 'https://invalid.example/project'
    rejected(values, 'invalid_scope_selector' if case == 'foreign_selector' else 'view_scope_provider_required')


@pytest.mark.parametrize('case', ['foreign_language', 'foreign_version', 'unknown_operator', 'nonboolean'])
def test_filter_contract_is_srx_one_and_requires_a_boolean_result(case):
    values = view_project(); program = values[-1]['filter']
    if case == 'foreign_language': program['language'] = 'python'
    elif case == 'foreign_version': program['version'] = '2.0'
    elif case == 'unknown_operator': program['expression'] = {'op': 'external.function'}
    else: program['expression'] = literal(1)
    rejected(values)


@pytest.mark.parametrize(('value', 'declared', 'reason'), [(None, 'string', 'view_column_value_type'),
    (False, 'number', 'view_column_value_type'), ({'state': 'missing'}, 'string', 'view_column_value_type'),
    ('absent', 'string', 'view_column_value_missing')])
def test_typed_cells_never_coerce_null_boolean_objects_or_absent_values(value, declared, reason):
    values = view_project()
    for artifact in values[:-1]: artifact['extensions'] = {'org.example': {'value': value}}
    pointer = '/extensions/org.example/absent' if value == 'absent' else '/extensions/org.example/value'
    values[-1]['columns'][0].update(source={'kind': 'artifact_field', 'pointer': pointer}, data_type=declared)
    rejected(values, reason, '/columns/0')


def test_escaped_field_names_and_exact_array_indices_preserve_inert_values():
    values = view_project(); text = '{{ execute() }} file:///tmp/source.json'
    for artifact in values[:-1]: artifact['extensions'] = {'org.example': {'a/b': {'~': [text]}}}
    values[-1]['columns'][0]['source']['pointer'] = '/extensions/org.example/a~1b/~0/0'
    with no_write_attempts(): data = resolve_view(bound_view_model(values), ref('VIEW')).data
    assert all(row['cells'][0] == {'type': 'string', 'value': text} for row in data['rows'])
    values[-1]['columns'][0]['source']['pointer'] = '/extensions/org.example/a~1b/~0/00'
    rejected(values, 'invalid_array_index')


@pytest.mark.parametrize('target', ['view', 'row'])
def test_original_byte_changes_rebind_sources_while_canonical_model_values_stay_equal(target):
    supplied = bound_view_model(); first = resolve_view(supplied, ref('VIEW'))
    identifier = ref('VIEW') if target == 'view' else aid(number=1)
    original = next(d for d in supplied.documents if json.loads(d.content)['id'] == identifier)
    raw = (json.dumps(json.loads(original.content), indent=3) + '\n').encode()
    documents = [ModelDocument(d.path, raw if d.path == original.path else d.content) for d in supplied.documents]
    updated = TargetModel(supplied.configuration_bytes, supplied.binding, documents,
                          profile=supplied.profile, resource_files=supplied.resource_files)
    with no_write_attempts(): second = resolve_view(updated, ref('VIEW'))
    old, new = first.data, second.data
    assert old['model_root_sha256'] == new['model_root_sha256']
    assert old['input_sha256'] != new['input_sha256']
    assert old['query_binding']['inputs_sha256'] != new['query_binding']['inputs_sha256']
    assert old['query_result'] == new['query_result'] and old['groups'] == new['groups']
    before, after = (old['view'], new['view']) if target == 'view' else (row_for(old), row_for(new))
    assert before['revision'] == after['revision'] and before['record_sha256'] == after['record_sha256']
    assert before['source_sha256'] != after['source_sha256'] == sha256(raw).hexdigest()
    if target == 'view': assert second.view_source_bytes == raw
    assert supplied.source_files[original.path] == original.content


def test_mutated_model_inputs_cannot_reuse_the_original_binding():
    supplied = bound_view_model(); documents = list(supplied.documents)
    documents[0] = ModelDocument(documents[0].path, documents[0].content + b'\n')
    object.__setattr__(supplied, 'documents', tuple(documents))
    with no_write_attempts(), pytest.raises(ModelError) as caught: resolve_view(supplied, ref('VIEW'))
    assert caught.value.reason == 'target_sources_changed'


@pytest.mark.parametrize('case', ['missing_target', 'noncanonical_symmetric', 'duplicate_edge_identity'])
def test_graph_errors_remain_errors_even_for_unused_projections_and_empty_selection(case):
    values = view_project(); values[-1]['filter'] = expression_document(literal(False))
    if case == 'missing_target': values[0]['relations'][0]['target'] = aid(number=99)
    elif case == 'noncanonical_symmetric':
        values[0]['relations'].pop(); values[3]['relations'] = [edge('conflicts_with', aid(number=1), number=4)]
    else: values[1]['relations'][0]['relation_id'] = values[0]['relations'][0]['relation_id']
    error = rejected(values, 'graph_model_invalid')
    assert error.actual in ('missing_relation_target', 'noncanonical_symmetric_relation', 'duplicate_relation_id')


def test_small_soft_graph_work_targets_do_not_truncate_declared_projection_depth():
    values = view_project()
    supplied = model(values, config=configuration_value(resource_limits={'srx_graph_steps': 1}))
    with no_write_attempts(): data = resolve_view(supplied, ref('VIEW')).data
    assert row_for(data)['relation_projections'] == {'ids': [aid(number=2), aid(number=3)], 'count': 2}


@pytest.mark.parametrize('invalid', [False, True])
def test_view_resolution_has_no_file_network_process_or_source_write_effects(tmp_path, monkeypatch, invalid):
    values = view_project(); values[0]['title'] = '{{ run() }} https://invalid.example/data'
    if invalid: values[-1]['relation_projections'][0]['aggregation'] = 'external.function'
    supplied = bound_view_model(values)
    for name, raw in supplied.source_files.items():
        path = tmp_path / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    before = inventory(tmp_path); calls = []
    def forbidden(*args, **kwargs):
        calls.append((args, kwargs)); raise AssertionError('Unexpected external operation')
    with no_write_attempts(), monkeypatch.context() as guard:
        for owner in (builtins, io, os): guard.setattr(owner, 'open', forbidden)
        guard.setattr(subprocess, 'Popen', forbidden); guard.setattr(os, 'system', forbidden)
        guard.setattr(socket, 'socket', forbidden)
        if invalid:
            with pytest.raises(ViewError) as caught: resolve_view(supplied, ref('VIEW'))
            assert caught.value.reason == 'view_relation_aggregation_required'
        else:
            data = resolve_view(supplied, ref('VIEW')).data
            assert row_for(data)['cells'][0]['value'] == values[0]['title']
    assert calls == [] and inventory(tmp_path) == before


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_isolated_core_and_pyz_resolve_identical_snapshot_view_values(tmp_path, mode):
    supplied = bound_view_model(); expected = resolve_view(supplied, ref('VIEW')).data
    body = '''import json
from specroad.changes import TargetModel
from specroad.documents import resolve_view
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
    body += 'print(json.dumps(resolve_view(owned,' + repr(ref('VIEW')) + ').data,sort_keys=True))\n'
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
