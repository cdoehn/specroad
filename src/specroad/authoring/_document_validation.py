"""Mandatory native document invariants for the common authoring target checks."""
from ..changes.request_ids import AuthoringError
from ..changes.target_model import TargetModel
from ..changes.values import ChangeOperation
from ..documents.roles import assess_document_roles
from ..documents.structure import assess_document_structure
from ..documents.includes import DocumentIncludeCycleError
from ..documents._include_graph import _include_graph
from ..model.canonical import canonical_json_sha256
from ..validation import ModelGate


def _document_gates(model, command_id, operations, gates, *, block_semantics=False):
    """Never let a host document service replace native command invariants."""
    owned = model.snapshot()
    operations = [ChangeOperation(operation).data for operation in operations]
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
        if command_id == 'section.move':
            from ._composition_preservation import _preserve_composition_sources
            _preserve_composition_sources(owned, context.documents, operations)
        proposed = target(context)
        primary = assess_document_roles(proposed).require_primary_document()
        assess_document_structure(proposed).require_document(primary['artifact_id'])
        _include_graph(proposed.documents, DocumentIncludeCycleError)
        if block_semantics:
            from ._document_mutation_validation import _block_semantics
            _block_semantics(proposed)
        return context.result()

    def document_sections(context):
        # The native field, reference, hierarchy, role and ownership checks
        # cover these two types. No block payload or view semantics is asserted.
        kinds = ('document', 'section', 'content_block') if block_semantics else ('document', 'section')
        if any(context.artifact(identity)['artifact_type'] not in kinds
               for identity in context.subjects):
            return context.result([{'reason': 'document_authoring_specialist_required', 'severity': 'error'}])
        return invariants(context)

    result = tuple(gates) + (ModelGate('extension:document-authoring',
        'document-authoring-v1', dependencies, invariants, binding),)
    if not any(type(gate) is ModelGate and gate.gate_id == 'document_model' for gate in gates):
        result += (ModelGate('document_model', 'document-section-authoring-v1',
            dependencies, document_sections, binding),)
    return result
