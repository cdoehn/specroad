"""Owned section ownership and contains-order observations over supplied bytes.

This is not rendering, include expansion, full document semantics or permission
to publish. The caller supplies the complete inventory; no files are discovered.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..graph.hierarchies import ordered_children, validate_hierarchies
from ..graph.references import RelationReferences
from ..graph.relations import SourceRelations
from ..graph.symmetry import require_canonical_relations
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.record_schemas import validate_record_fields
from ..storage.json_syntax import parse_json_object


class DocumentStructureError(ModelError):
    exit_code = 3


@dataclass(frozen=True, init=False)
class DocumentStructureAssessment:
    """Detached ordered structure derived from actual source-owned relations."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use assess_document_structure with actual model bytes')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return canonical_json_sha256(self.data)

    @property
    def structure_valid(self):
        return self.data['structure_valid']

    def require_document(self, document_id):
        """Return a detached document traversal, never a rendering approval."""
        data = self.data
        if not data['structure_valid']:
            issue = data['diagnostics'][0]
            raise DocumentStructureError(issue['reason'], path=issue.get('path'),
                                         pointer=issue.get('pointer', ''))
        if type(document_id) is not str:
            raise ModelError('document_id_required')
        for document in data['documents']:
            if document['document_id'] == document_id:
                return document
        raise DocumentStructureError('document_not_found', pointer='/document_id')

    def __bool__(self):
        raise TypeError('Use structure_valid explicitly; this is not full validation')


def assess_document_structure(model):
    """Evaluate every section's parent and ordered document composition.

    Every supplied section needs exactly one incoming contains relation, even
    when another document would otherwise be usable. Equal positions retain
    the native target-ID/relation-ID tie-breaker; input arrays are not sorted
    or rewritten. Primary-role, include and payload semantics remain separate.
    """
    from ..changes.target_model import TargetModel, _default_scope
    if type(model) is not TargetModel:
        raise ModelError('document_target_model_required')
    model = model.snapshot()
    records = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
    index = {r.identity.id: r for r in records}
    values = {identity: source.data for identity, source in index.items()}
    diagnostics = []
    for source in records:
        value = values[source.identity.id]
        if value['artifact_type'] not in ('document', 'section', 'content_block'):
            continue
        try:
            validate_record_fields(value)
        except ModelError as error:
            diagnostics.append({**error.diagnostic(), 'artifact_id': value['id'],
                                'path': source.path, 'severity': 'error'})
    fields_valid = not diagnostics
    if fields_valid:
        try:
            references = RelationReferences(records)
            require_canonical_relations(references)
            validate_hierarchies(references)
        except ModelError as error:
            diagnostics.append({**error.diagnostic(), 'severity': 'error'})
    owners, children, documents = [], {}, []
    if not diagnostics:
        incoming = {identity: [] for identity, value in values.items()
                    if value['artifact_type'] == 'section'}
        for edge in references.relations:
            if edge.relation.type == 'contains' and edge.target.id in incoming:
                incoming[edge.target.id].append(edge)
        for identity in sorted(incoming):
            edges = incoming[identity]
            if len(edges) != 1:
                diagnostics.append({'reason': 'document_section_parent_cardinality',
                    'path': index[identity].path, 'pointer': '', 'artifact_id': identity,
                    'parent_count': len(edges), 'related_ids': [e.source.id for e in edges],
                    'relation_ids': [e.relation.identity.id for e in edges], 'severity': 'error'})
            else:
                edge = edges[0]
                owners.append({'section_id': identity, 'parent_id': edge.source.id,
                               'relation_id': edge.relation.identity.id})
    if not diagnostics:
        for identity in sorted(values):
            if values[identity]['artifact_type'] not in ('document', 'section'):
                continue
            children[identity] = [{'artifact_id': edge.target.id,
                'artifact_type': edge.target.artifact_type,
                'relation_id': edge.relation.identity.id,
                'position': edge.relation.data['position'],
                'relation': edge.relation.data,
                'relation_sha256': canonical_json_sha256(edge.relation.data)}
                for edge in ordered_children(references, identity)]
        for identity in sorted(values):
            value = values[identity]
            if value['artifact_type'] != 'document':
                continue
            pending = [(identity, edge, 0) for edge in reversed(children[identity])]
            preorder = []
            while pending:
                parent, edge, depth = pending.pop()
                preorder.append({k: edge[k] for k in
                    ('artifact_id', 'artifact_type', 'relation_id', 'position')}
                    | {'parent_id': parent, 'depth': depth})
                if edge['artifact_type'] == 'section':
                    pending.extend((edge['artifact_id'], child, depth + 1)
                                   for child in reversed(children[edge['artifact_id']]))
            documents.append({'document_id': identity, 'revision': value['revision'],
                'root_section_ids': [edge['artifact_id'] for edge in children[identity]],
                'preorder': preorder})
    descriptor = _default_scope()
    data = {'format_version': 'document-structure-v1', 'project_id': model.binding.project_id,
        'scope_descriptor': descriptor,
        'model_root_sha256': model.manifest(model.artifacts, descriptor).sha256,
        'input_sha256': model._sources_sha256,
        'validation_scope': 'supplied_project_section_ownership_and_contains_order',
        'source_bindings': [{'artifact_id': r.identity.id, 'path': r.path,
            'source_sha256': sha256(r.source_bytes).hexdigest(),
            'record_sha256': canonical_json_sha256(values[r.identity.id])} for r in records],
        'document_fields_valid': fields_valid, 'structure_valid': not diagnostics,
        'diagnostics': diagnostics, 'section_owners': owners if not diagnostics else None,
        'children': children if not diagnostics else None,
        'documents': documents if not diagnostics else None,
        'project_files_verified': False, 'full_validation_passed': False,
        'primary_role_checked': False, 'include_graph_checked': False,
        'payload_semantics_checked': False, 'rendering_performed': False,
        'write_authorized': False, 'approval_granted': False}
    result = object.__new__(DocumentStructureAssessment)
    object.__setattr__(result, '_encoded', canonical_json_bytes(data))
    return result
