"""Snapshot-bound query and literal table data, without templates or rendering."""
from dataclasses import dataclass
from hashlib import sha256

from ..graph.references import RelationReferences
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.domain_schemas import DOMAIN_TYPES
from ..model.errors import ModelError
from ..query import NormalizedQuery, query_records
from ..srx.pointers import resolve_tokens
from ..storage.domain_artifact import DomainArtifact
from ..storage.json_syntax import parse_json_object
from ..storage.record_artifact import RecordArtifact
from .blocks import ContentBlock
from ._table_projection import TableProjection


class TableBlockError(ModelError):
    exit_code = 3


@dataclass(frozen=True, init=False)
class TableBlockData:
    """Owned block/view bytes and detached typed rows from one model snapshot."""
    block_source_bytes: bytes
    view_source_bytes: bytes | None
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use resolve_table_block with an owned TargetModel')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Table data is not rendering or project approval')


def resolve_table_block(model, block_id):
    """Resolve one query/table block without reading files or changing sources.

    The supplied project snapshot owns the selected block, view, configuration,
    relation graph and row values. General view grouping/relations and rendering
    remain separate providers. Missing providers fail before result creation.
    """
    from ..changes.target_model import TargetModel, _default_scope
    projection = TableProjection(TableBlockError)
    if type(model) is not TargetModel:
        raise ModelError('document_target_model_required')
    if type(block_id) is not str:
        raise TableBlockError('content_block_id_required', pointer='/block_id')
    model = model.snapshot()
    records = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
    index = {record.identity.id: record for record in records}
    source = index.get(block_id)
    if source is None:
        raise TableBlockError('content_block_not_found', pointer='/block_id')
    if source.identity.artifact_type != 'content_block':
        projection._fail('table_content_block_required', source, '/block_id')
    block = ContentBlock(source.source_bytes, path=source.path)
    if block.block_kind not in ('query', 'table'):
        projection._fail('table_content_block_required', source, '/block_kind')
    RelationReferences(records)
    payload = block.payload; view = None; view_bytes = None
    query = None; descriptor = None; query_page = None; query_binding = None
    configuration_id = None; column_source = source
    if payload.get('source') == 'view':
        position, relation = next((i, r) for i, r in enumerate(source.relations) if r.type == 'references')
        target = index[relation.target]
        stored = RecordArtifact(target.source_bytes, expected_type='view', path=target.path)
        value = stored.data; view_bytes = stored.source_bytes
        query, descriptor = projection._view_query(value, target, len(records))
        configuration_id = descriptor.data['configuration_id']
        view = {'artifact_id': value['id'], 'revision': value['revision'], 'path': target.path,
            'source_sha256': sha256(view_bytes).hexdigest(), 'record_sha256': canonical_json_sha256(value),
            'reference_id': relation.identity.id, 'reference_pointer': '/relations/' + str(position),
            'scope_descriptor': descriptor.data, 'scope_descriptor_sha256': descriptor.sha256}
        column_values = payload['columns'] if block.block_kind == 'query' else value['columns']
        if block.block_kind == 'table': column_source = target
    elif block.block_kind == 'query':
        query = NormalizedQuery.from_data(payload['query'])
        column_values = payload['columns']
    else:
        column_values = payload['columns']
    column_pointer = '/payload/columns' if column_source is source else '/columns'
    columns = projection._columns(column_values, column_source, column_pointer, literal=query is None)
    if query is None:
        rows = projection._literal_rows(payload, columns, source)
    else:
        page = query_records(records, query, project=model.configuration.data, configuration_id=configuration_id)
        query_page = page.data
        query_binding = {'query': query.data, 'query_sha256': page.query_sha256,
            'inputs_sha256': page.inputs_sha256, 'source_count': page.source_count,
            'configuration_binding': page.configuration_binding}
        rows = []
        for item in query_page['items']:
            record = index[item['id']]
            reader = DomainArtifact if record.identity.artifact_type in DOMAIN_TYPES else RecordArtifact
            artifact = reader(record.source_bytes, path=record.path).data
            cells = [projection._cell(resolve_tokens(artifact, column[0], rule_id='document-table', at=column[3]),
                           column, column_source) for column in columns]
            rows.append({'artifact_id': item['id'], 'artifact_type': item['artifact_type'],
                'revision': artifact['revision'], 'source_sha256': sha256(record.source_bytes).hexdigest(),
                'record_sha256': canonical_json_sha256(artifact), 'cells': cells})
    empty_policy = payload.get('empty_policy')
    if not rows and empty_policy == 'error':
        projection._fail('table_query_empty', source, '/payload/empty_policy')
    data = {'format_version': 1, 'kind': 'table-block-data-v1', 'project_id': model.binding.project_id,
        'scope_descriptor': _default_scope(),
        'model_root_sha256': model.manifest(model.artifacts, _default_scope()).sha256,
        'input_sha256': model._sources_sha256, 'block': block.binding, 'view': view,
        'columns': column_values, 'rows': rows, 'row_count': len(rows),
        'row_source': 'view' if view is not None else 'query' if query is not None else 'literal',
        'query_binding': query_binding, 'query_result': query_page,
        'empty_policy': empty_policy, 'outcome': 'rows' if rows else empty_policy or 'empty',
        'validation_scope': 'supplied_snapshot_table_projection',
        'project_files_verified': False, 'full_validation_passed': False,
        'document_structure_checked': False, 'rendering_performed': False,
        'write_authorized': False, 'approval_granted': False}
    result = object.__new__(TableBlockData)
    object.__setattr__(result, 'block_source_bytes', block.source_bytes)
    object.__setattr__(result, 'view_source_bytes', view_bytes)
    object.__setattr__(result, '_encoded', canonical_json_bytes(data))
    return result
