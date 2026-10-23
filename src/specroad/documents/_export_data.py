"""Pure schema and byte serializers for already resolved native view data.

No provider selection, query evaluation or filesystem publication happens here.
JSON and CSV share the exact same selected cells and source-bound metadata.
"""
import io

from .._metadata import __version__, MODEL_SCHEMA_VERSION
from ..model.canonical import canonical_json_bytes
from ..storage._csv_syntax import row_bytes


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


def view_export_data(model, view_id, data):
    """Build the shared export envelope without changing native values or scope."""
    rows = [{key: value for key, value in row.items() if key != 'relation_projections'}
            for row in data['rows']]
    return {'format_version': 1, 'kind': 'view-export-v1',
        'generated': True, 'normative': False, 'notice': 'GENERATED — DO NOT EDIT',
        'tool_version': __version__, 'schema_version': MODEL_SCHEMA_VERSION,
        'profiles': list(model.profile.profile_chain), 'project_id': data['project_id'],
        'model_root_sha256': data['model_root_sha256'], 'input_sha256': data['input_sha256'],
        'view_id': view_id, 'view_revision': data['view']['revision'],
        'view_source_sha256': data['view']['source_sha256'],
        'view_record_sha256': data['view']['record_sha256'],
        'export_scope': 'selected_view_columns', 'cell_encoding': 'typed-json-v1',
        'columns': data['columns'], 'rows': rows, 'row_count': len(rows), 'losses': []}


def csv_view_bytes(exported, *, source_path, error_type):
    """Encode admitted cells and their metadata as equal-width RFC-4180 records."""
    columns = exported['columns']
    rows = exported['rows']
    for number, column in enumerate(columns):
        if column['data_type'] in ('array', 'object') and 'serialization' not in column:
            raise error_type('view_csv_serialization_required',
                path=source_path, pointer='/columns/' + str(number))
    for row in rows:
        for number, cell in enumerate(row['cells']):
            if cell['type'] == 'missing' and 'serialization' not in columns[number]:
                raise error_type('view_csv_missing_encoding_required',
                    path=source_path, pointer='/columns/' + str(number))
    metadata = {key: value for key, value in exported.items() if key != 'rows'}
    metadata.update(kind='view-csv-v1', cell_encoding=('csv-columns-v1'
        if any('serialization' in column for column in columns) else 'csv-scalars-v1'),
        row_bindings=[{key: value for key, value in row.items() if key != 'cells'} for row in rows])
    stream = io.BytesIO()
    stream.write(row_bytes(['record_type', 'metadata', *[column['heading'] for column in columns]]))
    stream.write(row_bytes(['metadata', canonical_json_bytes(metadata).decode('utf-8'),
                           *['' for _ in columns]]))
    for row in rows:
        values = [canonical_json_bytes(cell).decode('utf-8') if 'serialization' in column
                  else cell['value'] if cell['type'] == 'string'
                  else canonical_json_bytes(cell['value']).decode('utf-8')
                  for column, cell in zip(columns, row['cells'])]
        stream.write(row_bytes(['data', '', *values]))
    return stream.getvalue()
