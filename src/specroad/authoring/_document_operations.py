"""Pure document intent translation to closed native graph-operation sequences.

Prepared identities and owned model bytes are data, never allocation or authority.
The shared authoring planner and writer retain validation and publication.
"""
from ..changes.request_ids import AuthoringError
from ..changes.target_model import TargetModel
from ..changes.values import ChangeOperation
from ..changes.relation_inputs import normalize_relation_add_input, _addition
from ..model.identity_values import ArtifactIdentity
from ..model.relation_values import RelationIdentity
from .creation import _draft
from .inputs import ArtifactCreateInput, normalize_artifact_create_input


def _document_operations(command_id, operations):
    if type(operations) not in (list, tuple):
        raise AuthoringError('document_operation_sequence_required')
    owned = [ChangeOperation(value).data for value in operations]
    shapes = {'document.create': ('create',), 'section.add': ('create', 'relation_add'),
              'section.move': ('relation_remove', 'relation_add')}
    if tuple(value['op'] for value in owned) != shapes[command_id]:
        raise AuthoringError('document_command_operation_mismatch')
    if command_id in ('document.create', 'section.add'):
        artifact = owned[0]['artifact']
        kind = 'document' if command_id == 'document.create' else 'section'
        if artifact['artifact_type'] != kind or artifact['relations']:
            raise AuthoringError('document_empty_creation_required')
    if command_id != 'document.create':
        relation = owned[1]['relation']
        if relation['type'] != 'contains':
            raise AuthoringError('document_contains_relation_required')
        if command_id == 'section.add' and relation['target'] != owned[0]['artifact']['id']:
            raise AuthoringError('document_created_section_target_required')
    return owned


def _creation(model, prepared, identity, kind, actor, planned_at):
    if (type(model) is not TargetModel or type(prepared) is not ArtifactCreateInput
            or type(identity) is not ArtifactIdentity or identity.artifact_type != kind):
        raise AuthoringError('typed_document_creation_inputs_required')
    data = prepared.data
    if data['artifact_type'] != kind:
        raise AuthoringError('document_creation_type_mismatch')
    normalized = normalize_artifact_create_input(kind, data['fields'])
    if normalized.source_bytes != prepared.source_bytes:
        raise AuthoringError('document_creation_input_changed')
    artifact = _draft(normalized, identity, actor, planned_at, model.snapshot().configuration)
    return {'op': 'create', 'artifact': artifact, 'result_id': identity.id}


def _contains(parent_id, section_id, identity, position, actor, planned_at):
    if type(identity) is not RelationIdentity:
        raise AuthoringError('typed_document_relation_identity_required')
    intent = normalize_relation_add_input(parent_id, 'contains', section_id, position=position)
    return _addition(intent, identity, actor, planned_at).data


def _move(model, section_id, *, parent_id, relation_identity, position,
          expected_relation_sha256, reason, actor, planned_at):
    if type(model) is not TargetModel or type(section_id) is not str:
        raise AuthoringError('typed_section_move_inputs_required')
    owned = model.snapshot()
    index = {value['id']: value for value in owned.artifacts}
    if index.get(section_id, {}).get('artifact_type') != 'section':
        raise AuthoringError('document_section_required', exit_code=3)
    incoming = [(value['id'], edge) for value in owned.artifacts for edge in value['relations']
                if edge['type'] == 'contains' and edge['target'] == section_id]
    if len(incoming) != 1:
        raise AuthoringError('document_original_section_relation_required', exit_code=3)
    source, edge = incoming[0]
    removal = {'op': 'relation_remove', 'source': source, 'relation_id': edge['relation_id'],
               'expected_sha256': expected_relation_sha256, 'reason': reason}
    addition = _contains(parent_id, section_id, relation_identity, position, actor, planned_at)
    return owned, [removal, addition]
