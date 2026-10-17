"""Declarative view data from an owned snapshot; no rendering or external I/O."""
from collections import deque
from dataclasses import dataclass
from hashlib import sha256
import unicodedata

from ..graph.relations import SourceRelations
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.domain_schemas import DOMAIN_TYPES
from ..model.errors import ModelError
from ..query import NormalizedQuery, query_records
from ..query.paging import _scalar_key
from ..srx import LoadedGraph, MISSING
from ..srx.errors import SrxError
from ..srx.graph_validation import validate_graph_node
from ..srx.pointers import parse_pointer, resolve_tokens
from ..srx.types import VALUE_TYPES, value_type
from ..storage.domain_artifact import DomainArtifact
from ..storage.json_syntax import parse_json_object
from ..storage.record_artifact import RecordArtifact


class ViewError(ModelError):
    exit_code = 3


@dataclass(frozen=True, init=False)
class ViewData:
    """Owned original view bytes and detached, typed snapshot projections."""
    view_source_bytes: bytes
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use resolve_view with an owned TargetModel')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('View data is not rendering or project approval')


def resolve_view(model, view_id):
    """Select project rows, project fields/relations and group typed values.

    The initial contract supports an unconfigured closed project scope, plain
    columns with missing=error, distinct related IDs/counts, and scalar grouping.
    Other scopes, computed status providers and rendering need their own bound
    services. A result never supplies those services or authorizes a write.
    """
    from ..changes.target_model import TargetModel, _default_scope
    if type(model) is not TargetModel:
        raise ModelError('document_target_model_required')
    if type(view_id) is not str:
        raise ViewError('view_id_required', pointer='/view_id')
    model = model.snapshot()
    records = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
    index = {record.identity.id: record for record in records}
    source = index.get(view_id)
    if source is None:
        raise ViewError('view_not_found', pointer='/view_id')

    def fail(reason, pointer):
        raise ViewError(reason, path=source.path, pointer=pointer)

    if source.identity.artifact_type != 'view':
        fail('view_record_required', '/view_id')
    stored = RecordArtifact(source.source_bytes, expected_type='view', path=source.path)
    value = stored.data
    descriptor = ScopeDescriptor(value['scope_descriptor'])
    if descriptor.scope_kind != 'project' or descriptor.data['boundary_policy'] != 'closed':
        fail('view_scope_provider_required', '/scope_descriptor')
    if descriptor.data['configuration_id'] is not None:
        fail('view_configuration_provider_required', '/scope_descriptor/configuration_id')

    # Every declaration is checked before filtering, including unused columns
    # and projections. An empty result cannot conceal an executable declaration.
    formats = value['formats']
    for i, name in enumerate(formats):
        if name not in ('json', 'markdown', 'html', 'csv'):
            fail('view_format_provider_required', '/formats/' + str(i))
        if name in formats[:i]:
            fail('view_format_duplicate', '/formats/' + str(i))
    projections = {}
    for i, projection in enumerate(value['relation_projections']):
        at = '/relation_projections/' + str(i)
        if (type(projection) is not dict
                or set(projection) != {'id', 'direction', 'types', 'max_depth', 'aggregation'}
                or type(projection['id']) is not str or not projection['id'].strip()
                or projection['id'].strip() != projection['id']
                or projection['id'] in projections):
            fail('view_relation_projection_contract', at)
        if projection['aggregation'] not in ('ids', 'count'):
            fail('view_relation_aggregation_required', at + '/aggregation')
        if type(projection['types']) is not list or not projection['types']:
            fail('view_relation_types_required', at + '/types')
        validate_graph_node({'op': 'reachable', 'where': {'op': 'literal', 'value': True},
            **{k: projection[k] for k in ('direction', 'types', 'max_depth')}},
            rule_id='document-view', at=at)
        projections[projection['id']] = projection

    columns = []
    for i, column in enumerate(value['columns']):
        at = '/columns/' + str(i)
        if (type(column) is not dict
                or set(column) != {'source', 'heading', 'data_type', 'format', 'missing'}
                or type(column['source']) is not dict
                or type(column['heading']) is not str or not column['heading'].strip()):
            fail('view_column_contract', at)
        if column['format'] != 'plain':
            fail('view_column_format_provider_required', at + '/format')
        if column['missing'] != 'error':
            fail('view_column_missing_provider_required', at + '/missing')
        if type(column['data_type']) is not str or column['data_type'] not in VALUE_TYPES[1:]:
            fail('view_column_data_type', at + '/data_type')
        selected = column['source']
        kind = selected.get('kind')
        if kind == 'artifact_field' and set(selected) == {'kind', 'pointer'}:
            try:
                tokens = parse_pointer(selected['pointer'], rule_id='document-view', at=at + '/source/pointer')
            except SrxError as error:
                raise ViewError('view_column_pointer_invalid', path=source.path, pointer=at + '/source/pointer') from error
            if not tokens:
                fail('view_column_field_required', at + '/source/pointer')
            if tokens[0] == 'verification_result':
                fail('query_verification_provider_required', at + '/source/pointer')
            columns.append((kind, tokens, column['data_type'], at))
        elif kind == 'relation_projection' and set(selected) == {'kind', 'projection_id'}:
            name = selected['projection_id']
            if type(name) is not str or name not in projections:
                fail('view_relation_projection_missing', at + '/source/projection_id')
            expected = 'array' if projections[name]['aggregation'] == 'ids' else 'number'
            if column['data_type'] != expected:
                fail('view_column_data_type', at + '/data_type')
            columns.append((kind, name, expected, at))
        else:
            fail('view_column_source_provider_required', at + '/source')

    grouping = []
    for i, group in enumerate(value['grouping']):
        at = '/grouping/' + str(i)
        if (type(group) is not dict or set(group) != {'column', 'direction'}
                or type(group['column']) is not int or not 0 <= group['column'] < len(columns)
                or group['direction'] not in ('asc', 'desc')
                or group['column'] in [number for number, _ in grouping]):
            fail('view_grouping_contract', at)
        if columns[group['column']][2] not in ('null', 'boolean', 'number', 'string'):
            fail('view_grouping_scalar_required', at + '/column')
        grouping.append((group['column'], group['direction']))
    ordering = []
    for i, item in enumerate(value['sort']):
        if (type(item) is not dict or set(item) != {'key', 'direction'}
                or type(item['key']) is not str or item['direction'] not in ('asc', 'desc')):
            fail('view_sort_contract', '/sort/' + str(i))
        ordering.append(item['key'] + ':' + item['direction'])
    query = NormalizedQuery(srx_filters=[value['filter']], sort=ordering, limit=len(records))
    page = query_records(records, query, project=model.configuration.data)
    graph = LoadedGraph(records, rule_id='document-view')

    def related(start, projection):
        # IDs, not walks or inverse edge views, are counted. The source is not
        # its own related target, even when a cycle leads back to it.
        seen, frontier = {start}, deque([(start, 0)])
        while frontier:
            current, depth = frontier.popleft()
            if depth >= projection['max_depth']:
                continue
            for edge in graph.neighbours(current, projection['direction'], projection['types']):
                target = edge.target.id
                if target not in seen:
                    seen.add(target)
                    frontier.append((target, depth + 1))
        targets = sorted(seen - {start})
        return targets if projection['aggregation'] == 'ids' else len(targets)

    rows = []
    for item in page.data['items']:
        record = index[item['id']]
        reader = DomainArtifact if record.identity.artifact_type in DOMAIN_TYPES else RecordArtifact
        artifact = reader(record.source_bytes, path=record.path).data
        projected = {name: related(item['id'], projection) for name, projection in projections.items()}
        cells = []
        for kind, selector, declared, at in columns:
            cell = (resolve_tokens(artifact, selector, rule_id='document-view', at=at)
                    if kind == 'artifact_field' else projected[selector])
            if cell is MISSING:
                fail('view_column_value_missing', at)
            actual = value_type(cell, rule_id='document-view')
            if actual != declared:
                fail('view_column_value_type', at)
            cells.append({'type': actual, 'value': cell})
        rows.append({'artifact_id': item['id'], 'artifact_type': item['artifact_type'],
            'revision': artifact['revision'], 'source_sha256': sha256(record.source_bytes).hexdigest(),
            'record_sha256': canonical_json_sha256(artifact), 'cells': cells,
            'relation_projections': projected})

    groups = {}
    for row in rows if grouping else ():
        cells = [row['cells'][number] for number, _ in grouping]
        keys = tuple(_scalar_key(cell['value'], '/grouping') for cell in cells)
        if keys not in groups:
            # Normalize grouping strings while preserving every original row
            # value. Numeric/bool/null keys retain their distinct SRX types.
            values = [{'type': cell['type'], 'value': unicodedata.normalize('NFC', cell['value'])
                       if cell['type'] == 'string' else cell['value']} for cell in cells]
            groups[keys] = {'keys': values, 'artifact_ids': []}
        groups[keys]['artifact_ids'].append(row['artifact_id'])
    group_keys = list(groups)
    for i in reversed(range(len(grouping))):
        group_keys.sort(key=lambda key: key[i], reverse=grouping[i][1] == 'desc')

    data = {'format_version': 1, 'kind': 'view-data-v1', 'project_id': model.binding.project_id,
        'scope_descriptor': _default_scope(),
        'model_root_sha256': model.manifest(model.artifacts, _default_scope()).sha256,
        'input_sha256': model._sources_sha256,
        'view': {'artifact_id': view_id, 'revision': value['revision'], 'path': source.path,
            'source_sha256': sha256(stored.source_bytes).hexdigest(),
            'record_sha256': canonical_json_sha256(value), 'scope_descriptor': descriptor.data,
            'scope_descriptor_sha256': descriptor.sha256},
        'columns': value['columns'], 'relation_projections': value['relation_projections'],
        'grouping': value['grouping'], 'formats': value['formats'],
        'rows': rows, 'row_count': len(rows), 'groups': [groups[key] for key in group_keys],
        'query_binding': {'query': query.data, 'query_sha256': page.query_sha256,
            'inputs_sha256': page.inputs_sha256, 'source_count': page.source_count,
            'configuration_binding': page.configuration_binding},
        'query_result': page.data, 'collation': 'srx-scalar-nfc-utf8-id-v1',
        'validation_scope': 'supplied_snapshot_view_projection', 'project_files_verified': False,
        'full_validation_passed': False, 'rendering_performed': False,
        'write_authorized': False, 'approval_granted': False}
    result = object.__new__(ViewData)
    object.__setattr__(result, 'view_source_bytes', stored.source_bytes)
    object.__setattr__(result, '_encoded', canonical_json_bytes(data))
    return result
