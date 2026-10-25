"""Cycle-checked document data composition over one owned project snapshot."""
from ._read_model import require_read_model, read_scope, read_root, partial_observation, local_references

from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from .structure import assess_document_structure
from ._include_graph import _edge_data, _include_graph


class DocumentIncludeError(ModelError):
    exit_code = 3


class DocumentIncludeCycleError(DocumentIncludeError):
    """A deterministic cycle of actual contains/include relation occurrences."""
    def __init__(self, edges, index, pointers):
        witness = [_edge_data(edge, index, pointers) for edge in edges]
        first = witness[0]
        super().__init__('document_include_cycle', path=first['path'], pointer=first['pointer'])
        self._cycle = canonical_json_bytes({
            'artifact_ids': [edge.source.id for edge in edges] + [edges[-1].target.id],
            'relation_ids': [edge.relation.identity.id for edge in edges], 'edges': witness})

    def diagnostic(self):
        return {**super().diagnostic(), **parse_json_object(self._cycle)}


@dataclass(frozen=True, init=False)
class DocumentComposition:
    """Detached occurrences share bound records; they never create stored copies."""
    _encoded: bytes
    _sources: tuple

    def __init__(self, *args, **kwargs):
        raise TypeError('Use compose_document with an owned TargetModel')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    @property
    def source_files(self):
        return dict(self._sources)

    def __bool__(self):
        raise TypeError('Document composition is not rendering or project approval')


def compose_document(model, document_id):
    """Check the whole supplied contains/include graph before expanding a root.

    Content includes retain a document container; section includes retain their
    section container. Occurrences describe data ancestry, not heading levels or
    rendered layout. Other block payloads remain passive for later providers.
    """
    from ..changes.target_model import TargetModel
    require_read_model(model)
    if type(document_id) is not str:
        raise DocumentIncludeError('document_id_required', pointer='/document_id')
    model = model.snapshot()
    structure = assess_document_structure(model)
    structure.require_document(document_id)
    index, pointers, edges, outgoing = _include_graph(model.documents, DocumentIncludeCycleError, model=model)
    # Repeated occurrences are deliberate. A global visited set here would
    # incorrectly drop content shared by two documents or include paths.
    pending = [(document_id, None, None, 0)]
    occurrences = []; used = set()
    while pending:
        identifier, parent, via, depth = pending.pop()
        value = index[identifier].data; number = len(occurrences); used.add(identifier)
        occurrences.append({'occurrence_index': number, 'artifact_id': identifier,
            'artifact_type': value['artifact_type'], 'revision': value['revision'],
            'parent_occurrence': parent, 'depth': depth, 'via': via})
        pending.extend((edge.target.id, number, _edge_data(edge, index, pointers), depth + 1)
                       for edge in reversed(outgoing.get(identifier, ())))
    bound_records = {}
    for identifier in sorted(used):
        source = index[identifier]; value = source.data
        bound_records[identifier] = {'artifact_id': identifier, 'artifact_type': value['artifact_type'],
            'revision': value['revision'], 'path': source.path,
            'source_sha256': sha256(source.source_bytes).hexdigest(),
            'record_sha256': canonical_json_sha256(value), 'record': value}
    observation = structure.data
    data = {'format_version': 1, 'kind': 'document-composition-v1',
        'project_id': observation['project_id'], 'scope_descriptor': observation['scope_descriptor'],
        'model_root_sha256': observation['model_root_sha256'], 'input_sha256': observation['input_sha256'],
        'document_id': document_id, 'document_revision': index[document_id].data['revision'],
        'structure_sha256': structure.sha256,
        'include_edges': [_edge_data(edge, index, pointers) for edge in sorted(edges,
            key=lambda edge: (edge.source.id, edge.target.id, edge.relation.identity.id))
            if edge.relation.type == 'references'],
        'occurrences': occurrences, 'occurrence_count': len(occurrences), 'records': bound_records,
        'validation_scope': 'supplied_snapshot_document_composition',
        'document_structure_checked': True, 'include_graph_checked': True, 'include_graph_acyclic': True,
        'project_files_verified': False, 'full_validation_passed': False,
        'primary_role_checked': False, 'payload_semantics_checked': False,
        'rendering_performed': False, 'write_authorized': False, 'approval_granted': False}
    result = object.__new__(DocumentComposition)
    object.__setattr__(result, '_encoded', canonical_json_bytes(data))
    object.__setattr__(result, '_sources', tuple(sorted((index[i].path, index[i].source_bytes) for i in used)))
    return result
