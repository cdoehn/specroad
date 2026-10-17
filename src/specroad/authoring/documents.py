"""Document intents translated to the common saved-plan authoring protocol.

The host supplies complete owned model/history inputs and prepared identities.
Previews allocate nothing and write nothing. Execute their saved Change Plan
through apply_authoring_plan, with fresh native checks and host authority.
This embedding API neither discovers project files nor registers a CLI writer.
"""
from ..changes.request_ids import AuthoringError
from ..changes.target_model import TargetModel
from ..changes.values import ChangeOperation
from ..changes.relation_inputs import normalize_relation_add_input, _addition
from ..documents.roles import assess_document_roles
from ..documents.structure import assess_document_structure
from ..documents.includes import DocumentIncludeCycleError
from ..documents._include_graph import _include_graph
from ..model.canonical import canonical_json_sha256
from ..model.identity_values import ArtifactIdentity
from ..model.relation_values import RelationIdentity
from ..validation import ModelGate
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


def _document_gates(model, command_id, operations, gates):
    """Never let a host document service replace native command invariants."""
    owned = model.snapshot()
    if command_id == 'section.move':
        removal, addition = operations
        matches = [edge for value in owned.artifacts if value['id'] == removal['source']
                   for edge in value['relations'] if edge['relation_id'] == removal['relation_id']]
        index = {value['id']: value for value in owned.artifacts}
        if (len(matches) != 1 or matches[0]['type'] != 'contains'
                or matches[0]['target'] != addition['relation']['target']
                or index.get(matches[0]['target'], {}).get('artifact_type') != 'section'):
            raise AuthoringError('document_original_section_relation_required', exit_code=3)
    if any(type(gate) is ModelGate and gate.gate_id == 'extension:document-authoring' for gate in gates):
        raise AuthoringError('document_authoring_gate_override')
    binding = canonical_json_sha256({'sources_sha256': owned._sources_sha256,
        'command_id': command_id, 'operations': operations})

    def dependencies(context):
        return context.dependency_result({identity: list(context.all_ids) for identity in context.subjects})

    def target(context):
        return TargetModel(owned.configuration_bytes, owned.binding, context.documents,
            profile=owned.profile, resource_files=owned.resource_files,
            attachments=owned.attachment_descriptors, language_packages=owned.language_packages,
            **owned.reservations)

    def invariants(context):
        proposed = target(context)
        primary = assess_document_roles(proposed).require_primary_document()
        assess_document_structure(proposed).require_document(primary['artifact_id'])
        _include_graph(proposed.documents, DocumentIncludeCycleError)
        return context.result()

    def document_sections(context):
        # The native field, reference, hierarchy, role and ownership checks
        # cover these two types. No block payload or view semantics is asserted.
        if any(context.artifact(identity)['artifact_type'] not in ('document', 'section')
               for identity in context.subjects):
            return context.result([{'reason': 'document_authoring_specialist_required', 'severity': 'error'}])
        return invariants(context)

    result = tuple(gates) + (ModelGate('extension:document-authoring',
        'document-authoring-v1', dependencies, invariants, binding),)
    if not any(type(gate) is ModelGate and gate.gate_id == 'document_model' for gate in gates):
        result += (ModelGate('document_model', 'document-section-authoring-v1',
            dependencies, document_sections, binding),)
    return result


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


def preview_document_create(model, prepared, *, identity, actor, planned_at, **options):
    """Prepare one empty document; primary-role validity is checked on target."""
    from .plans import preview_authoring_request
    operation = _creation(model, prepared, identity, 'document', actor, planned_at)
    return preview_authoring_request(model, 'document.create', [operation],
        actor=actor, planned_at=planned_at, **options)


def preview_section_add(model, prepared, *, identity, parent_id, relation_identity,
                        position, actor, planned_at, **options):
    """Create and attach one section in the same native Change Plan."""
    from .plans import preview_authoring_request
    creation = _creation(model, prepared, identity, 'section', actor, planned_at)
    addition = _contains(parent_id, identity.id, relation_identity, position, actor, planned_at)
    return preview_authoring_request(model, 'section.add', [creation, addition],
        actor=actor, planned_at=planned_at, **options)


def preview_section_move(model, section_id, *, parent_id, relation_identity, position,
                         expected_relation_sha256, reason, actor, planned_at, **options):
    """Replace the exact original ownership edge atomically, using a fresh ID.

    The caller retains the observed original relation hash as a precondition.
    The section record and descendants are not updated by these operations.
    """
    from .plans import preview_authoring_request
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
    return preview_authoring_request(owned, 'section.move', [removal, addition],
        actor=actor, planned_at=planned_at, **options)
