"""Language annotations beside unchanged native view/query/literal values."""
from ._read_model import require_read_model, read_scope, read_root, partial_observation, local_references

from dataclasses import dataclass
from hashlib import sha256

from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.content_language import ContentLanguage
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from .requirement_presentation import resolve_requirement_presentation
from .tables import resolve_table_block
from .views import resolve_view


@dataclass(frozen=True, init=False)
class TablePresentation:
    """Detached annotations and exact native projection, never approval."""
    source_bytes: bytes
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use resolve_view_presentation or resolve_table_presentation')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Table presentation is not semantic or release approval')


def _snapshot(model):
    from ..changes.target_model import TargetModel
    require_read_model(model)
    return model.snapshot()


def resolve_view_presentation(model, view_id, *, configuration_id=None):
    """Use exactly the native configured view selection and original cell values."""
    model = _snapshot(model)
    resolved = resolve_view(model, view_id, configuration_id=configuration_id)
    return _presentation(model, resolved, resolved.view_source_bytes)


def resolve_table_presentation(model, block_id):
    """Annotate an existing table/query block without changing its selection."""
    model = _snapshot(model)
    resolved = resolve_table_block(model, block_id)
    return _presentation(model, resolved, resolved.block_source_bytes)


def _presentation(model, resolved, source_bytes):
    projection = resolved.data
    records = [SourceRelations(d.content, path=d.path) for d in model.documents]
    sources = {r.identity.id: r for r in records}
    owner_id = parse_json_object(source_bytes)['id']
    definitions = {p['id']: p for p in projection.get('relation_projections', ())}
    meanings = {}
    rows = []
    # The native planner already rejects cyclic projection definitions. Traverse
    # only declared record projections, never objects that merely resemble one.
    pending = [(projection['rows'], projection['columns'], rows)]
    while pending:
        native_rows, columns, annotations = pending.pop()
        for row_number, row in enumerate(native_rows):
            identifier = row.get('artifact_id')
            source = sources[identifier if identifier is not None else owner_id]
            value = source.data
            language = ContentLanguage(value.get('language'), value.get('text_direction', 'auto')).as_dict()
            requirement = None
            if identifier is not None and source.identity.artifact_type == 'requirement':
                if identifier not in meanings:
                    meanings[identifier] = resolve_requirement_presentation(model, identifier).data
                requirement = meanings[identifier]
            bound = {'artifact_id': value['id'], 'artifact_type': value['artifact_type'],
                'revision': value['revision'], 'path': source.path,
                'source_sha256': sha256(source.source_bytes).hexdigest(),
                'record_sha256': canonical_json_sha256(value)}
            cells = []
            for number, (column, cell) in enumerate(zip(columns, row['cells'])):
                selected = column.get('source', {})
                definition = (definitions[selected['projection_id']]
                              if selected.get('kind') == 'relation_projection' else None)
                pointer = (column.get('field', selected.get('pointer')) if identifier is not None
                           else '/payload/rows/' + str(row_number) + '/' + str(number))
                field = (pointer[1:] if requirement is not None
                         and pointer in ('/statement', '/normative_force') else None)
                nested = [] if definition is not None and definition['aggregation'] == 'records' else None
                cells.append({'source_pointer': pointer, 'requirement_field': field,
                    'content_language': language if definition is None else None,
                    'records': nested})
                if nested is not None:
                    pending.append((cell['value'], definition['columns'], nested))
            annotations.append({'source': bound, 'source_kind': 'artifact' if identifier is not None else 'literal_block',
                'content_language': language,
                'text_direction_source': 'declaration' if 'text_direction' in value else 'default',
                'requirement': requirement, 'cells': cells})

    # NFC is a native collation key, not a replacement normative statement.
    # Group headings use the first actual row's unmodified typed cells and bind
    # that representative; every original variant remains in projection.rows.
    by_id = {row['artifact_id']: (row, annotation)
             for row, annotation in zip(projection['rows'], rows) if 'artifact_id' in row}
    groups = []
    for group in projection.get('groups', ()):
        identifier = group['artifact_ids'][0]
        row, annotation = by_id[identifier]
        numbers = [g['column'] for g in projection['grouping']]
        groups.append({'representative_artifact_id': identifier,
            'keys': [row['cells'][n] for n in numbers],
            'cells': [annotation['cells'][n] for n in numbers],
            'requirement': annotation['requirement']})
    data = {'format_version': 1, 'kind': 'table-presentation-v1',
        'projection': projection, 'projection_sha256': resolved.sha256,
        'rows': rows, 'groups': groups,
        'generated': True, 'normative': False,
        'validation_scope': 'supplied_snapshot_table_presentation',
        'language_policy_evaluated': False, 'language_registry_checked': False,
        'text_semantics_evaluated': False, 'translation_performed': False,
        'project_files_verified': False, 'full_validation_passed': False,
        'rendering_performed': False, 'write_authorized': False, 'approval_granted': False}
    result = object.__new__(TablePresentation)
    object.__setattr__(result, 'source_bytes', source_bytes)
    object.__setattr__(result, '_encoded', canonical_json_bytes(data))
    return result
