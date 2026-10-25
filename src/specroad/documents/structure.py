"""Owned section ownership and contains-order observations over supplied bytes.

This is not rendering, include expansion, full document semantics or permission
to publish. The caller supplies the complete inventory; no files are discovered.
"""
from ._read_model import require_read_model, read_scope, read_root, partial_observation, local_references

from dataclasses import dataclass
from hashlib import sha256

from ..graph.hierarchies import validate_hierarchies
from ..graph.references import RelationReferences
from ..graph.relations import SourceRelations
from ..graph.symmetry import require_canonical_relations
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.record_schemas import validate_record_fields
from ..storage.json_syntax import parse_json_object
from ._structure_graph import _document_structure


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


def assess_document_structure(model, *, scope_descriptor=None):
    """Evaluate every section's parent and ordered document composition.

    Every supplied section needs exactly one incoming contains relation, even
    when another document would otherwise be usable. Equal positions retain
    the native target-ID/relation-ID tie-breaker; input arrays are not sorted
    or rewritten. Primary-role, include and payload semantics remain separate.
    """
    from ..changes.target_model import TargetModel, _default_scope
    from ..graph.scope_descriptors import ScopeDescriptor
    require_read_model(model)
    descriptor = ScopeDescriptor(read_scope(model) if scope_descriptor is None else scope_descriptor).data
    if partial_observation(model) is not None and descriptor != read_scope(model):
        raise DocumentStructureError('document_partial_scope_mismatch', pointer='/scope_descriptor')
    if partial_observation(model) is None and (descriptor['scope_kind'] != 'project' or descriptor['boundary_policy'] != 'closed'
            or descriptor['configuration_id'] is not None):
        raise DocumentStructureError('document_structure_full_project_scope_required', pointer='/scope_descriptor')
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
            references = local_references(model, records)
            require_canonical_relations(references)
            validate_hierarchies(references)
        except ModelError as error:
            diagnostics.append({**error.diagnostic(), 'severity': 'error'})
    owners, children, documents = [], {}, []
    if not diagnostics:
        owners, children, documents, findings = _document_structure(records, references, values)
        diagnostics.extend(findings)
    data = {'format_version': 'document-structure-v1', 'project_id': model.binding.project_id,
        'scope_descriptor': descriptor,
        'model_root_sha256': read_root(model, descriptor),
        'input_sha256': model._sources_sha256,
        'validation_scope': ('supplied_project_section_ownership_and_contains_order'
            if partial_observation(model) is None else 'partial_section_ownership_and_contains_order'),
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
