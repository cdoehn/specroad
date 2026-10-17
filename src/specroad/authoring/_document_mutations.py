"""Closed block and section-removal plans using the native operation contracts."""
from ..changes.request_ids import AuthoringError
from ..changes.target_model import TargetModel
from ..changes.values import ChangeOperation
from ..documents.roles import assess_document_roles
from ..documents.structure import assess_document_structure
from ._document_operations import _contains


def _mutation_operations(command_id, operations):
    if type(operations) not in (list, tuple) or not operations:
        raise AuthoringError('document_operation_sequence_required')
    owned = [ChangeOperation(value).data for value in operations]
    kinds = tuple(value['op'] for value in owned)
    if command_id == 'block.add':
        if kinds != ('create', 'relation_add'):
            raise AuthoringError('document_command_operation_mismatch')
        artifact, edge = owned[0]['artifact'], owned[1]['relation']
        if (artifact['artifact_type'] != 'content_block' or edge['type'] != 'contains'
                or edge['target'] != artifact['id']):
            raise AuthoringError('document_created_block_target_required')
    elif command_id in ('block.update', 'block.remove'):
        if kinds != (('update',) if command_id == 'block.update' else ('retire',)):
            raise AuthoringError('document_command_operation_mismatch')
    elif command_id == 'section.remove':
        cascade = all(kind == 'retire' for kind in kinds)
        moves = kinds[0] == 'retire' and kinds[1:] == ('relation_remove', 'relation_add') * ((len(kinds) - 1) // 2)
        if not (cascade or moves):
            raise AuthoringError('document_command_operation_mismatch')
    else:
        raise AuthoringError('supported_authoring_command_required')
    return owned


def _removal_inventory(model, section_id):
    primary = assess_document_roles(model).require_primary_document()
    structure = assess_document_structure(model)
    structure.require_document(primary['artifact_id'])
    index = {value['id']: value for value in model.artifacts}
    if index.get(section_id, {}).get('artifact_type') != 'section':
        raise AuthoringError('document_section_required', exit_code=3)
    children = {key: sorted((edge for edge in value['relations'] if edge['type'] == 'contains'),
        key=lambda edge: (edge['position'], edge['target'], edge['relation_id']))
        for key, value in index.items()}
    pending = [section_id]; descendants = []
    while pending:
        identity = pending.pop()
        if identity in descendants:
            raise AuthoringError('document_removal_shared_child', exit_code=3)
        descendants.append(identity)
        pending.extend(edge['target'] for edge in reversed(children[identity]))
    return index, children, descendants


def _mutation_scope(model, command_id, operations):
    """Validate saved operations against actual owners, not only convenience flags."""
    index = {value['id']: value for value in model.artifacts}
    if command_id == 'block.add':
        if index.get(operations[1]['source'], {}).get('artifact_type') != 'section':
            raise AuthoringError('document_block_parent_required', exit_code=3)
        return
    if command_id in ('block.update', 'block.remove'):
        if index.get(operations[0]['target'], {}).get('artifact_type') != 'content_block':
            raise AuthoringError('document_content_block_required', exit_code=3)
        return
    root = operations[0]['target']
    index, children, descendants = _removal_inventory(model, root)
    if all(op['op'] == 'retire' for op in operations):
        if [op['target'] for op in operations] != descendants:
            raise AuthoringError('document_complete_retirement_required', exit_code=3)
        removed = set(descendants)
        if any(edge['target'] in removed - {root} and source not in removed
               for source, edges in children.items() for edge in edges):
            raise AuthoringError('document_removal_shared_child', exit_code=3)
        return
    pairs = list(zip(operations[1::2], operations[2::2]))
    if len(pairs) != len(children[root]):
        raise AuthoringError('document_all_children_move_required', exit_code=3)
    destinations = {addition['source'] for _, addition in pairs}
    if len(destinations) != 1:
        raise AuthoringError('document_one_children_destination_required', exit_code=3)
    destination = next(iter(destinations))
    if (destination in descendants or index.get(destination, {}).get('artifact_type') != 'section'
            or index[destination]['maturity'] == 'retired'):
        raise AuthoringError('document_children_destination_required', exit_code=3)
    for original, (removal, addition) in zip(children[root], pairs):
        edge = addition['relation']
        if (removal['source'] != root or removal['relation_id'] != original['relation_id']
                or edge['type'] != 'contains' or edge['target'] != original['target']):
            raise AuthoringError('document_original_child_relation_required', exit_code=3)


def _section_removal(model, retirement, *, cascade, move_children_to,
                     child_retirements, child_moves, actor, planned_at):
    if (type(model) is not TargetModel or type(retirement) is not ChangeOperation
            or retirement.op != 'retire' or type(cascade) is not bool
            or type(child_retirements) not in (tuple, list) or type(child_moves) not in (tuple, list)):
        raise AuthoringError('typed_section_remove_inputs_required')
    owned = model.snapshot(); retirement = ChangeOperation(retirement.data)
    root = retirement.data['target']
    _, children, _ = _removal_inventory(owned, root)
    if (cascade and move_children_to is not None or not cascade and child_retirements
            or move_children_to is None and child_moves):
        raise AuthoringError('document_removal_strategy_conflict')
    if children[root] and not cascade and move_children_to is None:
        raise AuthoringError('document_removal_strategy_required')
    operations = [retirement.data]
    if cascade:
        if any(type(op) is not ChangeOperation or op.op != 'retire' for op in child_retirements):
            raise AuthoringError('typed_child_retirements_required')
        operations.extend(op.data for op in child_retirements)
    elif move_children_to is not None:
        if type(move_children_to) is not str or len(child_moves) != len(children[root]):
            raise AuthoringError('document_all_children_move_required')
        if not children[root]:
            raise AuthoringError('document_children_move_requires_children')
        for edge, move in zip(children[root], child_moves):
            if type(move) is not dict or set(move) != {'target', 'relation_identity', 'position', 'expected_relation_sha256'}:
                raise AuthoringError('typed_child_move_required')
            if move['target'] != edge['target']:
                raise AuthoringError('document_original_child_relation_required')
            operations.append({'op': 'relation_remove', 'source': root,
                'relation_id': edge['relation_id'], 'expected_sha256': move['expected_relation_sha256'],
                'reason': retirement.data['reason']})
            operations.append(_contains(move_children_to, edge['target'], move['relation_identity'],
                move['position'], actor, planned_at))
    return owned, operations
