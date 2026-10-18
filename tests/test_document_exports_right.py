"""Declared lossless cell codecs, output boundaries and real failure states."""
from copy import deepcopy
import csv
import io
import json
import os

import pytest

from specroad.documents import (ViewError, ViewExportError, export_view, resolve_view,
                               view_export_schema, write_view_export)
from specroad.documents import _export_output as output
from specroad.model._schema import validate_builtin
from specroad.model.errors import ModelError
from specroad.security import SafetyViolation
from support.read_only import no_write_attempts
from support.records import ref
from support.srx import expression_document, literal
from support.targets import model
from test_document_exports import disk_project, file_bytes, expected_rows, scalar_project
from test_document_view_variants import variant_project
from test_document_view_variants_right import field_column, nested_project
from test_document_views import view_project


def encoded_project(nested=False):
    values = nested_project() if nested else view_project()
    values[-1]['formats'] = ['json', 'csv']
    for column in values[-1]['columns']:
        if column['data_type'] in ('array', 'object'):
            column['serialization'] = {'csv': 'typed-json-v1'}
    return values


def read_columns_csv(raw):
    records = list(csv.reader(io.StringIO(raw.decode('utf-8'), newline=''), strict=True))
    data = json.loads(records[1][1]); columns = data['columns']
    assert data['kind'] == 'view-csv-v1' and data['cell_encoding'] == 'csv-columns-v1'
    assert all(len(record) == len(columns) + 2 for record in records)
    assert records[1][0] == 'metadata' and records[1][2:] == [''] * len(columns)
    assert len(records) - 2 == data['row_count'] == len(data['row_bindings'])
    rows = []
    for record, binding in zip(records[2:], data['row_bindings']):
        assert record[:2] == ['data', '']
        cells = []
        for value, column in zip(record[2:], columns):
            if 'serialization' in column:
                assert column['serialization'] == {'csv': 'typed-json-v1'}
                cells.append(json.loads(value))
            else:
                cells.append({'type': column['data_type'], 'value': value
                    if column['data_type'] == 'string' else json.loads(value)})
        rows.append({**binding, 'cells': cells})
    return data, rows


@pytest.mark.parametrize('nested', [False, True])
@pytest.mark.parametrize('output_format', ['json', 'csv'])
def test_explicit_codec_preserves_actual_nested_projection_values_and_bindings(nested, output_format):
    supplied = model(encoded_project(nested)); before = supplied.source_files
    with no_write_attempts(): raw = export_view(supplied, ref('VIEW'), output_format=output_format)
    if output_format == 'json':
        data = json.loads(raw); validate_builtin(data, view_export_schema()); rows = data['rows']
    else:
        data, rows = read_columns_csv(raw)
    assert rows == expected_rows(supplied)
    assert data['losses'] == [] and supplied.source_files == before


@pytest.mark.parametrize(('present', 'kind'), [(None, 'null'), (False, 'boolean'), (0, 'number'),
    ('', 'string'), ('null', 'string'), ('a,"\r\né', 'string'),
    ([], 'array'), ({}, 'object'), ([{'v': [None, False, 0, '']}], 'array')])
def test_typed_csv_distinguishes_missing_null_and_every_present_cell(present, kind):
    values = scalar_project()
    for artifact in values[:-1]: artifact['extensions'] = {'org.example': {'value': present}}
    del values[0]['extensions']['org.example']['value']
    column = field_column('/extensions/org.example/value', kind, 'preserve')
    column['serialization'] = {'csv': 'typed-json-v1'}
    values[-1].update(columns=[column], grouping=[])
    supplied = model(values)
    data, rows = read_columns_csv(export_view(supplied, ref('VIEW'), output_format='csv'))
    assert rows == expected_rows(supplied)
    assert [row['cells'][0] for row in rows].count({'type': 'missing'}) == 1
    assert [row['cells'][0] for row in rows].count({'type': kind, 'value': present}) == 3
    assert data['columns'] == [column]


def test_empty_view_keeps_declared_codecs_without_inventing_data():
    values = encoded_project(True); values[-1]['filter'] = expression_document(literal(False))
    data, rows = read_columns_csv(export_view(model(values), ref('VIEW'), output_format='csv'))
    assert rows == [] and data['row_count'] == 0 and data['losses'] == []


@pytest.mark.parametrize('empty', [False, True])
@pytest.mark.parametrize('serialization', [None, 'typed-json-v1', {}, [],
    {'csv': 'json'}, {'csv': ['typed-json-v1']}, {'html': 'typed-json-v1'},
    {'csv': 'typed-json-v1', 'loader': 'external.function'}])
def test_unknown_serialization_contracts_fail_before_export_even_without_rows(empty, serialization):
    values = scalar_project(); values[-1]['columns'][0]['serialization'] = serialization
    if empty: values[-1]['filter'] = expression_document(literal(False))
    supplied = model(values)
    with no_write_attempts(), pytest.raises(ViewError) as caught:
        export_view(supplied, ref('VIEW'), output_format='csv')
    assert caught.value.reason == 'view_column_serialization_contract'
    assert caught.value.pointer == '/columns/0/serialization'


@pytest.mark.parametrize('unused', [False, True])
def test_nested_declarations_are_checked_and_never_authorize_the_outer_column(unused):
    values = nested_project(); view = values[-1]; view['formats'] = ['csv']
    view['relation_projections'][0]['columns'][0]['serialization'] = {'csv': 'typed-json-v1'}
    if unused: view['filter'] = expression_document(literal(False))
    with pytest.raises(ViewExportError) as caught:
        export_view(model(values), ref('VIEW'), output_format='csv')
    assert caught.value.reason == 'view_csv_serialization_required'
    view['relation_projections'][1]['columns'][0]['serialization'] = {'csv': 'execute'}
    with pytest.raises(ViewError) as caught:
        export_view(model(values), ref('VIEW'), output_format='csv')
    assert caught.value.pointer == '/relation_projections/1/columns/0/serialization'


@pytest.mark.parametrize('platform', ['linux', 'windows'])
@pytest.mark.parametrize('declared', [False, True])
def test_csv_uses_the_actual_configured_rows_and_graph(platform, declared):
    values = variant_project(platform, declared=declared); view = values[-2]
    view['formats'] = ['csv']; view['columns'][2]['serialization'] = {'csv': 'typed-json-v1'}
    supplied = model(values); kwargs = {} if declared else {'configuration_id': ref('CFG')}
    expected = resolve_view(supplied, ref('VIEW'), **kwargs).data['rows']
    data, rows = read_columns_csv(export_view(supplied, ref('VIEW'), output_format='csv', **kwargs))
    assert rows == [{key: value for key, value in row.items() if key != 'relation_projections'} for row in expected]
    assert data['row_count'] == (3 if platform == 'linux' else 4)


def test_declared_serialization_does_not_enable_file_process_or_network_loading(monkeypatch):
    import builtins
    supplied = model(encoded_project(True)); before = supplied.source_files
    def forbidden(*args, **kwargs): raise AssertionError('unexpected source loading')
    with no_write_attempts(), monkeypatch.context() as patch:
        patch.setattr(builtins, 'open', forbidden)
        patch.setattr(io, 'open', forbidden)
        patch.setattr(os, 'open', forbidden)
        raw = export_view(supplied, ref('VIEW'), output_format='csv')
    assert read_columns_csv(raw)[1] == expected_rows(supplied)
    assert supplied.source_files == before


def test_schema_rejects_foreign_codec_and_never_mutates_its_prior_instance():
    data = json.loads(export_view(model(encoded_project()), ref('VIEW')))
    schema = view_export_schema(); validate_builtin(data, schema)
    damaged = deepcopy(data); damaged['columns'][2]['serialization']['csv'] = 'execute'
    with pytest.raises(ModelError): validate_builtin(damaged, schema)
    validate_builtin(data, view_export_schema())


@pytest.mark.parametrize('output_format', ['json', 'csv'])
def test_explicit_external_target_is_atomic_and_leaves_the_entire_project_unchanged(tmp_path, output_format, monkeypatch):
    root, source, supplied = disk_project(tmp_path, values=encoded_project(True))
    external = tmp_path / 'exports'; external.mkdir(); (external / 'reports').mkdir()
    before = file_bytes(root)
    def forbidden(*args): raise AssertionError('generated output acquired a project lock')
    monkeypatch.setattr(output.LockFiles, 'acquire', forbidden)
    path = 'reports/view.' + output_format
    receipt = write_view_export(supplied, ref('VIEW'), source=source, path=path,
                                output_root=external, output_format=output_format)
    assert file_bytes(root) == before
    assert file_bytes(external) == {path: export_view(supplied, ref('VIEW'), output_format=output_format)}
    assert receipt['path'] == str(external / path) and receipt['normative'] is False


@pytest.mark.parametrize('kind', ['same', 'child', 'ancestor', 'foreign', 'foreign_child',
    'symlink', 'symlink_parent', 'operational', 'reserved', 'missing', 'file', 'relative'])
def test_external_root_cannot_relabel_projects_links_or_operational_paths(tmp_path, kind):
    root, source, supplied = disk_project(tmp_path)
    external = tmp_path / 'exports'; external.mkdir()
    destination = external
    if kind == 'same': destination = root
    elif kind == 'child': destination = root / 'generated'
    elif kind == 'ancestor': destination = tmp_path
    elif kind in ('foreign', 'foreign_child'):
        (external / 'specroad.json').write_bytes(b'foreign project')
        if kind == 'foreign_child': destination = external / 'reports'; destination.mkdir()
    elif kind in ('symlink', 'symlink_parent'):
        destination = tmp_path / 'linked'; destination.symlink_to(external, target_is_directory=True)
        if kind == 'symlink_parent': (external / 'reports').mkdir(); destination = destination / 'reports'
    elif kind in ('operational', 'reserved'):
        destination = external / ('.specroad' if kind == 'operational' else '.git'); destination.mkdir()
    elif kind == 'missing': destination = external / 'absent'
    elif kind == 'file': destination = external / 'file'; destination.write_bytes(b'prior')
    else: destination = 'relative'
    before = file_bytes(root); external_before = file_bytes(external)
    with pytest.raises((ModelError, SafetyViolation, OSError)):
        write_view_export(supplied, ref('VIEW'), source=source, path='view.json', output_root=destination)
    assert file_bytes(root) == before and file_bytes(external) == external_before


@pytest.mark.parametrize('path', ['.specroad/out.json', '.git/out.json', '.patchharbor/out.json',
    'specroad.json', 'nested/specroad.json', '../outside.json', '/absolute.json'])
def test_forbidden_relative_paths_remain_forbidden_with_an_external_root(tmp_path, path):
    root, source, supplied = disk_project(tmp_path); external = tmp_path / 'exports'; external.mkdir()
    before = file_bytes(root)
    with pytest.raises(ModelError):
        write_view_export(supplied, ref('VIEW'), source=source, path=path, output_root=external)
    assert file_bytes(root) == before and file_bytes(external) == {}


@pytest.mark.parametrize('external_target', [False, True])
def test_concurrent_target_creation_cannot_be_overwritten(tmp_path, monkeypatch, external_target):
    root, source, supplied = disk_project(tmp_path); external = tmp_path / 'exports'; external.mkdir()
    directory = external if external_target else root / 'generated'; before = file_bytes(root)
    original = os.link
    def appeared(src, dst, **kwargs):
        (directory / 'view.json').write_bytes(b'concurrent output')
        return original(src, dst, **kwargs)
    monkeypatch.setattr(os, 'link', appeared)
    with pytest.raises(ViewExportError) as caught:
        write_view_export(supplied, ref('VIEW'), source=source,
            path='view.json' if external_target else 'generated/view.json',
            output_root=external if external_target else None)
    assert caught.value.reason == 'view_export_target_exists' and caught.value.exit_code == 6
    assert (directory / 'view.json').read_bytes() == b'concurrent output'
    assert all(file_bytes(root)[name] == raw for name, raw in before.items())


@pytest.mark.parametrize('change', ['directory', 'symlink', 'nested_project', 'configuration', 'image'])
def test_changes_after_private_preparation_prevent_final_publication(tmp_path, monkeypatch, change):
    root, source, supplied = disk_project(tmp_path); before = file_bytes(root)
    original = output._write_new
    def altered(directory, name, raw):
        identity = original(directory, name, raw)
        generated = root / 'generated'
        if change in ('directory', 'symlink'):
            generated.rename(root / 'saved-generated')
            if change == 'directory': generated.mkdir()
            else: generated.symlink_to(root / 'spec', target_is_directory=True)
        elif change == 'nested_project': (generated / 'specroad.json').write_bytes(b'foreign')
        elif change == 'configuration': (root / 'specroad.json').write_bytes(b'changed')
        else: (generated / name).write_bytes(b'changed')
        return identity
    monkeypatch.setattr(output, '_write_new', altered)
    with pytest.raises((ModelError, SafetyViolation)):
        write_view_export(supplied, ref('VIEW'), source=source, path='generated/view.json')
    assert not (root / 'generated/view.json').exists()
    assert not (root / 'spec/view.json').exists()
    after = file_bytes(root)
    assert all(after[name] == raw for name, raw in before.items()
               if not (change == 'configuration' and name == 'specroad.json'))


@pytest.mark.parametrize('change', ['root', 'foreign_marker'])
def test_external_root_is_rechecked_before_publication(tmp_path, monkeypatch, change):
    root, source, supplied = disk_project(tmp_path); external = tmp_path / 'exports'; external.mkdir()
    before = file_bytes(root); original = output._write_new
    def altered(directory, name, raw):
        identity = original(directory, name, raw)
        if change == 'root': external.rename(tmp_path / 'old-exports'); external.mkdir()
        else: (external / 'specroad.json').write_bytes(b'foreign project')
        return identity
    monkeypatch.setattr(output, '_write_new', altered)
    with pytest.raises((ModelError, SafetyViolation)):
        write_view_export(supplied, ref('VIEW'), source=source, path='view.json', output_root=external)
    assert not (external / 'view.json').exists() and file_bytes(root) == before


def test_failure_after_atomic_publication_retains_complete_bytes_and_never_reports_success(tmp_path, monkeypatch):
    root, source, supplied = disk_project(tmp_path); before = file_bytes(root)
    raw = export_view(supplied, ref('VIEW')); published = False
    link, fsync = os.link, os.fsync
    def publish(*args, **kwargs):
        nonlocal published
        link(*args, **kwargs); published = True
        assert (root / 'generated/view.json').read_bytes() == raw
    def fail_after_link(fd):
        if published: raise OSError('synthetic directory durability failure')
        return fsync(fd)
    with monkeypatch.context() as patch:
        patch.setattr(os, 'link', publish); patch.setattr(os, 'fsync', fail_after_link)
        with pytest.raises(OSError):
            write_view_export(supplied, ref('VIEW'), source=source, path='generated/view.json')
    assert (root / 'generated/view.json').read_bytes() == raw
    assert all(file_bytes(root)[name] == content for name, content in before.items())
    retained = file_bytes(root)
    with pytest.raises(ViewExportError):
        write_view_export(supplied, ref('VIEW'), source=source, path='generated/view.json')
    assert file_bytes(root) == retained
