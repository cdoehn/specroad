"""Declarative view data from an owned snapshot; no rendering or external I/O."""
from dataclasses import dataclass
from hashlib import sha256
import unicodedata

from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..query.paging import _scalar_key
from ..srx import MISSING
from ..storage.json_syntax import parse_json_object
from ..storage.record_artifact import RecordArtifact
from ._view_definition import plan_view
from ._view_projection import project_view_rows
from ._view_selection import select_view


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
    selected_scope, page, graph = select_view(records, model.configuration.data, index,
        descriptor, query, configuration_id, fail)
    rows = project_view_rows(index, graph, projections, columns, projection_columns, page, fail)

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
