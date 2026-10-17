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
from ..srx.pointers import resolve_tokens
from ..srx.types import value_type
from ..storage.domain_artifact import DomainArtifact
from ..storage.json_syntax import parse_json_object
from ..storage.record_artifact import RecordArtifact
from ._view_definition import plan_view


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


def resolve_view(model, view_id, *, configuration_id=None):
    """Select project rows, project fields/relations and group typed values.

    The contract supports a closed project scope, plain columns with explicit
    missing policy, bounded related IDs/counts/records, and scalar grouping.
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
    descriptor, projections, columns, projection_columns, grouping, query = plan_view(
        value, source, len(records), ViewError)
    selected_scope = descriptor.data
    if configuration_id is not None:
        if selected_scope['configuration_id'] not in (None, configuration_id):
            fail('view_configuration_conflict', '/scope_descriptor/configuration_id')
        selected_scope['configuration_id'] = configuration_id
    selected_scope = ScopeDescriptor(selected_scope)
    selected_id = selected_scope.data['configuration_id']
    if selected_id is not None and selected_id not in index:
        fail('view_configuration_provider_required', '/scope_descriptor/configuration_id')
    page = query_records(records, query, project=model.configuration.data, configuration_id=selected_id)
    eligible_ids = None
    if selected_id is not None:
        # Resolve the same native configuration over all snapshot records.
        # The row filter must not discard applicable intermediate graph nodes.
        eligible = query_records(records, NormalizedQuery(limit=len(records)),
            project=model.configuration.data, configuration_id=selected_id)
        eligible_ids = [item['id'] for item in eligible.data['items']]
    graph = LoadedGraph(records, rule_id='document-view', artifact_ids=eligible_ids)

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
        return sorted(seen - {start})

    artifacts = {}
    projected_values = {}

    def bound_row(artifact_id, planned_columns):
        record = index[artifact_id]
        if artifact_id not in artifacts:
            reader = DomainArtifact if record.identity.artifact_type in DOMAIN_TYPES else RecordArtifact
            artifacts[artifact_id] = reader(record.source_bytes, path=record.path).data
        artifact = artifacts[artifact_id]
        cells = []
        for kind, selector, declared, missing, at in planned_columns:
            cell = (resolve_tokens(artifact, selector, rule_id='document-view', at=at)
                    if kind == 'artifact_field' else projected_values[artifact_id, selector])
            if cell is MISSING:
                if missing == 'error':
                    fail('view_column_value_missing', at)
                cells.append({'type': 'missing'})
                continue
            actual = value_type(cell, rule_id='document-view')
            if actual != declared:
                fail('view_column_value_type', at)
            cells.append({'type': actual, 'value': cell})
        return {'artifact_id': artifact_id, 'artifact_type': record.identity.artifact_type,
            'revision': artifact['revision'], 'source_sha256': sha256(record.source_bytes).hexdigest(),
            'record_sha256': canonical_json_sha256(artifact), 'cells': cells}

    def project(start, name):
        # Definition cycles are rejected by the planner. Evaluate the remaining
        # DAG iteratively, including shared children, without Python recursion.
        pending = [(start, name, None)]
        while pending:
            current, selected, targets = pending.pop()
            key = current, selected
            if key in projected_values:
                continue
            projection = projections[selected]
            if targets is None:
                targets = related(current, projection)
                if projection['aggregation'] != 'records':
                    projected_values[key] = (len(targets) if projection['aggregation'] == 'count' else targets)
                    continue
                pending.append((current, selected, targets))
                dependencies = [selector for kind, selector, _, _, _ in projection_columns[selected]
                                if kind == 'relation_projection']
                pending.extend((target, dependency, None)
                               for target in reversed(targets) for dependency in reversed(dependencies))
            else:
                projected_values[key] = [bound_row(target, projection_columns[selected]) for target in targets]
        return projected_values[start, name]

    rows = []
    for item in page.data['items']:
        projected = {name: project(item['id'], name) for name in projections}
        rows.append({**bound_row(item['id'], columns), 'relation_projections': projected})

    groups = {}
    for row in rows if grouping else ():
        cells = [row['cells'][number] for number, _ in grouping]
        keys = tuple(_scalar_key(cell.get('value', MISSING), '/grouping') for cell in cells)
        if keys not in groups:
            # Normalize grouping strings while preserving every original row
            # value. Numeric/bool/null keys retain their distinct SRX types.
            values = [({'type': 'string', 'value': unicodedata.normalize('NFC', cell['value'])}
                       if cell['type'] == 'string' else dict(cell)) for cell in cells]
            groups[keys] = {'keys': values, 'artifact_ids': []}
        groups[keys]['artifact_ids'].append(row['artifact_id'])
    group_keys = list(groups)
    for i in reversed(range(len(grouping))):
        group_keys.sort(key=lambda key: key[i], reverse=grouping[i][1] == 'desc')

    data = {'format_version': 1, 'kind': 'view-data-v1', 'project_id': model.binding.project_id,
        'scope_descriptor': _default_scope(),
        'model_root_sha256': model.manifest(model.artifacts, _default_scope()).sha256,
        'input_sha256': model._sources_sha256,
        'selection_scope_descriptor': selected_scope.data,
        'selection_scope_descriptor_sha256': selected_scope.sha256,
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
