"""Machine-readable values and actual generated-file effects, not presentation."""
import csv
from hashlib import sha256
import io
import json
import os

import pytest

from specroad.documents import (ViewExportError, export_view, resolve_view,
                               view_export_schema, write_view_export)
from specroad.model._schema import validate_builtin
from specroad.model.errors import ModelError
from specroad.model.model_manifest import ProjectReadBinding
from specroad.security import SafetyViolation
from specroad.storage.project import ProjectSource
from support.read_only import no_write_attempts
from support.records import ref
from support.targets import model
from test_document_views import view_project
from test_document_view_variants_right import field_column, nested_project
from support.srx import expression_document, literal


def scalar_project():
    values = view_project()
    values[-1].update(columns=values[-1]['columns'][:2], relation_projections=[],
                      formats=['json', 'csv'])
    return values


def read_csv(raw):
    records = list(csv.reader(io.StringIO(raw.decode('utf-8'), newline=''), strict=True))
    metadata = json.loads(records[1][1])
    assert all(len(record) == 2 + len(metadata['columns']) for record in records)
    assert records[0][:2] == ['record_type', 'metadata']
    assert records[1][0] == 'metadata'
    assert records[1][2:] == [''] * len(metadata['columns'])
    rows = []
    for record, binding in zip(records[2:], metadata['row_bindings']):
        assert record[:2] == ['data', '']
        cells = [{'type': column['data_type'], 'value': value if column['data_type'] == 'string'
                  else json.loads(value)} for column, value in zip(metadata['columns'], record[2:])]
        rows.append({**binding, 'cells': cells})
    assert len(rows) == len(records) - 2 == metadata['row_count'] == len(metadata['row_bindings'])
    return metadata, rows


def expected_rows(supplied):
    return [{key: value for key, value in row.items() if key != 'relation_projections'}
            for row in resolve_view(supplied, ref('VIEW')).data['rows']]


@pytest.mark.parametrize('nested', [False, True])
def test_json_roundtrip_preserves_typed_cells_row_order_and_actual_bindings(nested):
    values = nested_project() if nested else scalar_project()
    values[-1]['formats'] = ['json']
    supplied = model(values); before = supplied.source_files
    with no_write_attempts(): raw = export_view(supplied, ref('VIEW'))
    document = json.loads(raw)
    validate_builtin(document, view_export_schema())
    assert document['rows'] == expected_rows(supplied)
    assert document['columns'] == values[-1]['columns']
    assert document['model_root_sha256'] == resolve_view(supplied, ref('VIEW')).data['model_root_sha256']
    assert document['input_sha256'] == supplied._sources_sha256
    assert document['losses'] == [] and document['normative'] is False
    assert document['export_scope'] == 'selected_view_columns'
    assert supplied.source_files == before


@pytest.mark.parametrize(('value', 'kind'), [(None, 'null'), (False, 'boolean'), (0, 'number'),
    ('', 'string'), ([1, None, {'k': 'v'}], 'array'), ({'a': [False, 'ä']}, 'object')])
def test_json_keeps_missing_separate_from_present_values(value, kind):
    values = scalar_project()
    for item in values[:-1]: item['extensions'] = {'org.example': {'value': value}}
    del values[0]['extensions']['org.example']['value']
    values[-1]['columns'] = [field_column('/extensions/org.example/value', kind, 'preserve')]
    values[-1]['grouping'] = []
    supplied = model(values)
    document = json.loads(export_view(supplied, ref('VIEW')))
    validate_builtin(document, view_export_schema())
    assert document['rows'] == expected_rows(supplied)
    cells = [row['cells'][0] for row in document['rows']]
    assert cells.count({'type': 'missing'}) == 1
    assert cells.count({'type': kind, 'value': value}) == 3


@pytest.mark.parametrize('value', ['comma,value', 'a"quoted" value', 'CR\rLF\nCRLF\r\n',
                                 'ä — 日本語', '', '=1+1', 'null', 'false'])
def test_csv_parser_recovers_original_strings_without_loss_or_formula_rewriting(value):
    values = scalar_project()
    for item in values[:-1]: item['extensions'] = {'org.example': {'value': value}}
    values[-1]['columns'][1] = field_column('/extensions/org.example/value', 'string')
    supplied = model(values)
    with no_write_attempts(): raw = export_view(supplied, ref('VIEW'), output_format='csv')
    metadata, rows = read_csv(raw)
    assert rows == expected_rows(supplied)
    assert metadata['cell_encoding'] == 'csv-scalars-v1' and metadata['losses'] == []
    assert metadata['model_root_sha256'] == resolve_view(supplied, ref('VIEW')).data['model_root_sha256']


@pytest.mark.parametrize(('value', 'kind'), [(None, 'null'), (False, 'boolean'),
    (True, 'boolean'), (0, 'number'), (-3.5, 'number'), (9007199254740991, 'number')])
def test_csv_scalar_types_roundtrip_using_the_embedded_column_schema(value, kind):
    values = scalar_project()
    for item in values[:-1]: item['extensions'] = {'org.example': {'value': value}}
    values[-1]['columns'] = [field_column('/extensions/org.example/value', kind)]
    values[-1]['grouping'] = []
    supplied = model(values)
    _, rows = read_csv(export_view(supplied, ref('VIEW'), output_format='csv'))
    assert rows == expected_rows(supplied)
    assert all(type(row['cells'][0]['value']) is type(value) for row in rows)


@pytest.mark.parametrize('output_format', ['json', 'csv'])
def test_empty_selection_keeps_a_parseable_schema_and_no_invented_rows(output_format):
    values = scalar_project(); values[-1]['filter'] = expression_document(literal(False))
    raw = export_view(model(values), ref('VIEW'), output_format=output_format)
    if output_format == 'json':
        document = json.loads(raw); validate_builtin(document, view_export_schema())
        assert document['row_count'] == 0 and document['rows'] == []
    else:
        metadata, rows = read_csv(raw)
        assert metadata['row_count'] == 0 and rows == []


@pytest.mark.parametrize('output_format', ['json', 'csv'])
def test_same_snapshot_and_reordered_input_inventory_produce_same_data_bytes(output_format):
    values = scalar_project()
    assert export_view(model(values), ref('VIEW'), output_format=output_format) == export_view(
        model(list(reversed(values))), ref('VIEW'), output_format=output_format)


@pytest.mark.parametrize('empty', [False, True])
def test_nested_csv_values_require_a_declared_provider_even_for_empty_views(empty):
    values = view_project(); values[-1]['formats'] = ['csv']
    if empty: values[-1]['filter'] = expression_document(literal(False))
    with no_write_attempts(), pytest.raises(ViewExportError) as caught:
        export_view(model(values), ref('VIEW'), output_format='csv')
    assert caught.value.reason == 'view_csv_serialization_required'
    assert caught.value.pointer == '/columns/2'


def test_csv_never_collapses_missing_to_empty_string_or_null():
    values = scalar_project()
    values[-1]['columns'] = [field_column('/extensions/org.example/absent', 'string', 'preserve')]
    values[-1]['grouping'] = []
    with pytest.raises(ViewExportError) as caught:
        export_view(model(values), ref('VIEW'), output_format='csv')
    assert caught.value.reason == 'view_csv_missing_encoding_required'


@pytest.mark.parametrize('output_format', ['html', '', None, [], 1])
def test_unknown_formats_are_rejected_before_querying_or_loading(output_format):
    with no_write_attempts(), pytest.raises(ViewExportError) as caught:
        export_view(None, 'unused', output_format=output_format)
    assert caught.value.reason == 'view_export_format_not_supported'


@pytest.mark.parametrize('output_format', ['json', 'csv'])
def test_format_must_be_declared_by_the_owned_view(output_format):
    values = scalar_project(); values[-1]['formats'] = ['markdown']
    with pytest.raises(ViewExportError) as caught:
        export_view(model(values), ref('VIEW'), output_format=output_format)
    assert caught.value.reason == 'view_export_format_not_declared'


@pytest.mark.parametrize('damage', ['unknown_field', 'wrong_cell_type', 'missing_value', 'normative'])
def test_json_schema_rejects_malformed_machine_contracts(damage):
    document = json.loads(export_view(model(scalar_project()), ref('VIEW')))
    if damage == 'unknown_field': document['executable'] = 'no'
    elif damage == 'wrong_cell_type': document['rows'][0]['cells'][0]['value'] = 3
    elif damage == 'missing_value': document['rows'][0]['cells'][0].pop('value')
    else: document['normative'] = True
    with pytest.raises(ModelError): validate_builtin(document, view_export_schema())


def disk_project(tmp_path, *, values=None, generated='generated'):
    from support.model import configuration_value, put
    root = tmp_path / 'project'; root.mkdir()
    values = values if values is not None else scalar_project()
    config = configuration_value(generated_path=generated)
    observed = model(values, config=config)
    for name, raw in observed.source_files.items(): put(root, name, raw)
    put(root, '.specroad/keep', b'operational bytes')
    (root / generated).mkdir(parents=True)
    source = ProjectSource(root)
    supplied = model(values, config=config, binding=ProjectReadBinding('sample', str(root),
        source.boundary._root_identity))
    return root, source, supplied


def file_bytes(root):
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob('*') if path.is_file() and not path.is_symlink()}


@pytest.mark.parametrize('output_format', ['json', 'csv'])
@pytest.mark.parametrize('generated', ['generated', 'reports/derived'])
def test_atomic_export_creates_only_the_explicit_generated_file(tmp_path, output_format, generated):
    root, source, supplied = disk_project(tmp_path, generated=generated)
    before = file_bytes(root); target = generated + '/view.' + output_format
    receipt = write_view_export(supplied, ref('VIEW'), source=source, path=target, output_format=output_format)
    after = file_bytes(root); raw = after.pop(target)
    assert after == before
    assert raw == export_view(supplied, ref('VIEW'), output_format=output_format)
    assert receipt['sha256'] == sha256(raw).hexdigest() and receipt['size'] == len(raw)
    assert receipt['normative'] is receipt['full_validation_passed'] is receipt['approval_granted'] is False
    if output_format == 'json': validate_builtin(json.loads(raw), view_export_schema())
    else: assert read_csv(raw)[1] == expected_rows(supplied)


@pytest.mark.parametrize('target', ['specroad.json', 'spec/requirements/out.json',
    '.specroad/out.json', 'attachments/out.json', 'archive/objects/out.json',
    'unmanaged/out.json', 'generated', 'generated/.specroad/out.json', 'generated/specroad.json',
    '../outside.json', '/tmp/outside.json', 'generated/../specroad.json'])
def test_forbidden_output_targets_leave_all_project_and_operational_bytes_unchanged(tmp_path, target):
    root, source, supplied = disk_project(tmp_path); before = file_bytes(root)
    with pytest.raises(ModelError): write_view_export(supplied, ref('VIEW'), source=source, path=target)
    assert file_bytes(root) == before


@pytest.mark.parametrize('kind', ['regular', 'symlink', 'directory', 'fifo'])
def test_existing_destinations_are_never_replaced_or_opened(tmp_path, kind):
    root, source, supplied = disk_project(tmp_path); target = root / 'generated/view.json'
    if kind == 'regular': target.write_bytes(b'prior output')
    elif kind == 'symlink': target.symlink_to(root / 'specroad.json')
    elif kind == 'directory': target.mkdir()
    else: os.mkfifo(target)
    before = file_bytes(root); original = target.lstat()
    with pytest.raises(ViewExportError) as caught:
        write_view_export(supplied, ref('VIEW'), source=source, path='generated/view.json')
    assert caught.value.reason == 'view_export_target_exists' and caught.value.exit_code == 6
    assert target.lstat() == original and file_bytes(root) == before


@pytest.mark.parametrize('kind', ['symlink', 'nested_project', 'missing'])
def test_output_directory_must_already_belong_to_the_single_project(tmp_path, kind):
    root, source, supplied = disk_project(tmp_path)
    target = root / 'generated/child'
    if kind == 'symlink': target.symlink_to(root / 'spec', target_is_directory=True)
    elif kind == 'nested_project':
        target.mkdir(); (target / 'specroad.json').write_bytes(b'{}')
    before = file_bytes(root)
    with pytest.raises((ModelError, SafetyViolation)):
        write_view_export(supplied, ref('VIEW'), source=source, path='generated/child/view.json')
    assert file_bytes(root) == before


def test_source_root_binding_cannot_be_reused_for_a_different_project(tmp_path):
    root, source, supplied = disk_project(tmp_path)
    other = tmp_path / 'other'; other.mkdir(); (other / 'specroad.json').write_bytes(source.configuration_bytes)
    (other / 'generated').mkdir()
    before = file_bytes(root); other_before = file_bytes(other)
    with pytest.raises(ViewExportError) as caught:
        write_view_export(supplied, ref('VIEW'), source=ProjectSource(other), path='generated/view.json')
    assert caught.value.reason == 'view_export_source_mismatch'
    assert file_bytes(root) == before and file_bytes(other) == other_before


def test_unsupported_csv_cannot_create_even_a_temporary_output(tmp_path):
    values = view_project(); values[-1]['formats'] = ['csv']
    root, source, supplied = disk_project(tmp_path, values=values); before = file_bytes(root)
    with pytest.raises(ViewExportError):
        write_view_export(supplied, ref('VIEW'), source=source, path='generated/view.csv', output_format='csv')
    assert file_bytes(root) == before


def test_prepublication_write_failure_preserves_inputs_and_never_exposes_partial_target(tmp_path, monkeypatch):
    root, source, supplied = disk_project(tmp_path); before = file_bytes(root)
    original_write = os.write
    def broken(fd, raw):
        original_write(fd, raw[:7])
        raise OSError('synthetic full disk')
    monkeypatch.setattr(os, 'write', broken)
    with pytest.raises(OSError):
        write_view_export(supplied, ref('VIEW'), source=source, path='generated/view.json')
    assert not (root / 'generated/view.json').exists()
    after = file_bytes(root)
    assert {key: after[key] for key in before} == before
    assert len(set(after) - set(before)) == 1
    assert all(key.startswith('generated/.view-export-') for key in set(after) - set(before))
