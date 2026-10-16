"""Full supplied-project document fields and primary-specification selection.

This narrow assessment does not discover files, validate document composition,
render output, grant write permission or replace the shared model validation.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.record_schemas import validate_record_fields
from ..storage.json_syntax import parse_json_object


class DocumentRoleError(ModelError):
    exit_code = 3


@dataclass(frozen=True, init=False)
class DocumentRoleAssessment:
    """Owned field/cardinality findings and the exact selected stored record."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use assess_document_roles with actual model bytes')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return canonical_json_sha256(self.data)

    @property
    def roles_valid(self):
        return self.data['roles_valid']

    def require_primary_document(self):
        """Return owned selection data, never rendering or publication approval."""
        data = self.data
        if not data['roles_valid']:
            issue = data['diagnostics'][0]
            raise DocumentRoleError(issue['reason'], path=issue.get('path'),
                                    pointer=issue.get('pointer', ''))
        return data['primary_document']

    def __bool__(self):
        raise TypeError('Use roles_valid explicitly; this is not full validation')


def assess_document_roles(model, *, scope_descriptor=None):
    """Check all document records and exactly one non-retired primary.

    TargetModel owns the complete supplied inventory, not a proof of completeness
    on disk. This API uses the full-project contract; it provides no partial or
    legacy fallback and never substitutes a first or supporting document.
    """
    from ..changes.target_model import TargetModel, _default_scope
    from ..graph.scope_descriptors import ScopeDescriptor
    if type(model) is not TargetModel:
        raise ModelError('document_target_model_required')
    descriptor = ScopeDescriptor(_default_scope() if scope_descriptor is None else scope_descriptor).data
    if (descriptor['scope_kind'] != 'project' or descriptor['boundary_policy'] != 'closed'
            or descriptor['configuration_id'] is not None):
        raise DocumentRoleError('document_full_project_scope_required', pointer='/scope_descriptor')
    model = model.snapshot()
    documents, primary, diagnostics = [], [], []
    for source in model.documents:
        record = parse_json_object(source.content, path=source.path)
        if record['artifact_type'] != 'document':
            continue
        documents.append({'artifact_id': record['id'], 'path': source.path,
            'source_sha256': sha256(source.content).hexdigest(),
            'record_sha256': canonical_json_sha256(record)})
        try:
            validate_record_fields(record, expected_type='document')
        except ModelError as error:
            diagnostics.append({**error.diagnostic(), 'artifact_id': record['id'],
                                'path': source.path, 'severity': 'error'})
            continue
        if record['maturity'] != 'retired' and record['document_role'] == 'primary_specification':
            primary.append({'artifact_id': record['id'], 'revision': record['revision'],
                'path': source.path, 'record_sha256': canonical_json_sha256(record),
                'record': record})
    fields_valid = not diagnostics
    # An invalid record may conceal its role; do not invent a second cardinality
    # finding from a partial set of successfully parsed document fields.
    if fields_valid and len(primary) != 1:
        diagnostics.append({'reason': 'document_primary_missing' if not primary else 'document_primary_multiple',
            'path': None, 'pointer': '/document_role', 'artifact_id': None,
            'related_ids': [row['artifact_id'] for row in primary], 'severity': 'error'})
    data = {'format_version': 'document-roles-v1', 'project_id': model.binding.project_id,
        'scope_descriptor': descriptor,
        'model_root_sha256': model.manifest(model.artifacts, descriptor).sha256,
        'input_sha256': model._sources_sha256,
        'validation_scope': 'supplied_full_project_document_fields_and_primary_role',
        'documents': documents, 'document_fields_valid': fields_valid,
        'active_primary_count': len(primary) if fields_valid else None,
        'roles_valid': not diagnostics, 'diagnostics': diagnostics,
        'primary_document': primary[0] if not diagnostics else None,
        'project_files_verified': False, 'full_validation_passed': False,
        'composition_validated': False, 'rendering_performed': False,
        'write_authorized': False, 'approval_granted': False}
    result = object.__new__(DocumentRoleAssessment)
    object.__setattr__(result, '_encoded', canonical_json_bytes(data))
    return result
