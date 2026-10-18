"""Versioned, non-normative exports of the native selected view columns.

JSON retains typed cells, including missing and nested values. CSV admits them
only with an explicit per-column typed JSON declaration. Neither adapter evaluates a second
query, reads project paths, imports values, or authorizes a normative write.
"""
import csv
import io

from .._metadata import __version__, MODEL_SCHEMA_VERSION
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from .views import resolve_view


class ViewExportError(ModelError):
    def __init__(self, reason, *, path=None, pointer='', exit_code=3):
        super().__init__(reason, path=path, pointer=pointer)
        self.exit_code = exit_code


def view_export_schema():
    """Closed JSON shape; native resolution enforces types and source bindings."""
    def obj(fields):
        return {'type': 'object', 'properties': fields,
                'required': sorted(fields), 'additionalProperties': False}

    def array(items):
        return {'type': 'array', 'items': items}

    text = {'type': 'string'}
    digest = {'type': 'string', 'pattern': r'^[0-9a-f]{64}(?![\s\S])'}
    revision = {'type': 'integer', 'minimum': 1}
    cell = {'anyOf': [obj({'type': {'const': 'missing'}}), *[
        obj({'type': {'const': kind}, 'value': {'type': kind}})
        for kind in ('null', 'boolean', 'number', 'string', 'array', 'object')]]}
    column = obj({'source': {'type': 'object'}, 'heading': text,
                  'data_type': {'enum': ['null', 'boolean', 'number', 'string', 'array', 'object']},
                  'format': {'const': 'plain'}, 'missing': {'enum': ['error', 'preserve']}})
    column['properties']['serialization'] = obj({'csv': {'const': 'typed-json-v1'}})
    row = obj({'artifact_id': text, 'artifact_type': text, 'revision': revision,
               'source_sha256': digest, 'record_sha256': digest, 'cells': array(cell)})
    return obj({'format_version': {'const': 1}, 'kind': {'const': 'view-export-v1'},
        'generated': {'const': True}, 'normative': {'const': False},
        'notice': {'const': 'GENERATED — DO NOT EDIT'}, 'tool_version': text,
        'schema_version': text, 'profiles': array(text), 'project_id': text,
        'model_root_sha256': digest, 'input_sha256': digest,
        'view_id': text, 'view_revision': revision,
        'view_source_sha256': digest, 'view_record_sha256': digest,
        'export_scope': {'const': 'selected_view_columns'},
        'cell_encoding': {'const': 'typed-json-v1'},
        'columns': array(column), 'rows': array(row),
        'row_count': {'type': 'integer', 'minimum': 0}, 'losses': {'const': []}})


def export_view(model, view_id, *, output_format='json', configuration_id=None):
    """Return owned UTF-8 data bytes; presentation rendering remains separate.

CSV uses RFC-4180 records of equal width: a header, one metadata record, then
data records. The metadata includes column types and ordered row bindings.
Only selected cells are exported; unselected fields, groups and auxiliary
projections are outside this explicitly declared export scope.
"""
    from ..changes.target_model import TargetModel
    if type(output_format) is not str or output_format not in ('json', 'csv'):
        raise ViewExportError('view_export_format_not_supported', pointer='/output_format')
    if type(model) is not TargetModel:
        raise ModelError('document_target_model_required')
    model = model.snapshot()
    data = resolve_view(model, view_id, configuration_id=configuration_id).data
    if output_format not in data['formats']:
        raise ViewExportError('view_export_format_not_declared',
                              path=data['view']['path'], pointer='/formats')
    rows = [{key: value for key, value in row.items() if key != 'relation_projections'}
            for row in data['rows']]
    exported = {'format_version': 1, 'kind': 'view-export-v1',
        'generated': True, 'normative': False, 'notice': 'GENERATED — DO NOT EDIT',
        'tool_version': __version__, 'schema_version': MODEL_SCHEMA_VERSION,
        'profiles': list(model.profile.profile_chain), 'project_id': data['project_id'],
        'model_root_sha256': data['model_root_sha256'], 'input_sha256': data['input_sha256'],
        'view_id': view_id, 'view_revision': data['view']['revision'],
        'view_source_sha256': data['view']['source_sha256'],
        'view_record_sha256': data['view']['record_sha256'],
        'export_scope': 'selected_view_columns', 'cell_encoding': 'typed-json-v1',
        'columns': data['columns'], 'rows': rows, 'row_count': len(rows), 'losses': []}
    if output_format == 'json':
        return canonical_json_bytes(exported)

    for number, column in enumerate(data['columns']):
        if column['data_type'] in ('array', 'object') and 'serialization' not in column:
            raise ViewExportError('view_csv_serialization_required',
                path=data['view']['path'], pointer='/columns/' + str(number))
    for row in rows:
        for number, cell in enumerate(row['cells']):
            if cell['type'] == 'missing' and 'serialization' not in data['columns'][number]:
                raise ViewExportError('view_csv_missing_encoding_required',
                    path=data['view']['path'], pointer='/columns/' + str(number))
    metadata = {key: value for key, value in exported.items() if key != 'rows'}
    metadata.update(kind='view-csv-v1', cell_encoding=('csv-columns-v1'
        if any('serialization' in column for column in data['columns']) else 'csv-scalars-v1'),
        row_bindings=[{key: value for key, value in row.items() if key != 'cells'} for row in rows])
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, dialect='excel', lineterminator='\r\n')
    writer.writerow(['record_type', 'metadata', *[column['heading'] for column in data['columns']]])
    writer.writerow(['metadata', canonical_json_bytes(metadata).decode('utf-8'),
                     *['' for _ in data['columns']]])
    for row in rows:
        values = [canonical_json_bytes(cell).decode('utf-8') if 'serialization' in column
                  else cell['value'] if cell['type'] == 'string'
                  else canonical_json_bytes(cell['value']).decode('utf-8')
                  for column, cell in zip(data['columns'], row['cells'])]
        writer.writerow(['data', '', *values])
    return stream.getvalue().encode('utf-8')
