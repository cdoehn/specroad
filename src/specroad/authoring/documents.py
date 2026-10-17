"""Document intents translated to the common saved-plan authoring protocol.

The host supplies complete owned model/history inputs and prepared identities.
Previews allocate nothing and write nothing. Execute their saved Change Plan
through apply_authoring_plan, with fresh native checks and host authority.
This embedding API neither discovers project files nor registers a CLI writer.
"""
from ._document_operations import _creation, _attached_creation, _single_operation, _move


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
    operations = _attached_creation(model, prepared, identity, 'section', parent_id=parent_id,
        relation_identity=relation_identity, position=position, actor=actor, planned_at=planned_at)
    return preview_authoring_request(model, 'section.add', operations,
        actor=actor, planned_at=planned_at, **options)


def preview_section_move(model, section_id, *, parent_id, relation_identity, position,
                         expected_relation_sha256, reason, actor, planned_at, **options):
    """Replace the exact original ownership edge atomically, using a fresh ID.

    The caller retains the observed original relation hash as a precondition.
    The section record and descendants are not updated by these operations.
    """
    from .plans import preview_authoring_request
    owned, operations = _move(model, section_id, parent_id=parent_id,
        relation_identity=relation_identity, position=position,
        expected_relation_sha256=expected_relation_sha256, reason=reason,
        actor=actor, planned_at=planned_at)
    return preview_authoring_request(owned, 'section.move', operations,
        actor=actor, planned_at=planned_at, **options)


def preview_block_add(model, prepared, *, identity, parent_id, relation_identity,
                      position, actor, planned_at, **options):
    """Create a prepared block and its contains edge in one saved native plan."""
    from .plans import preview_authoring_request
    operations = _attached_creation(model, prepared, identity, 'content_block', parent_id=parent_id,
        relation_identity=relation_identity, position=position, actor=actor, planned_at=planned_at)
    return preview_authoring_request(model, 'block.add', operations,
        actor=actor, planned_at=planned_at, **options)


def preview_block_update(model, operation, *, actor, planned_at, **options):
    """Use the caller's retained native update guards and RFC-6902 patch."""
    from .plans import preview_authoring_request
    operations = _single_operation(operation, 'typed_block_update_required')
    return preview_authoring_request(model, 'block.update', operations,
        actor=actor, planned_at=planned_at, **options)


def preview_block_remove(model, operation, *, actor, planned_at, **options):
    """Retire a guarded block, retaining its stored identity and relations."""
    from .plans import preview_authoring_request
    operations = _single_operation(operation, 'typed_block_retirement_required')
    return preview_authoring_request(model, 'block.remove', operations,
        actor=actor, planned_at=planned_at, **options)


def preview_section_remove(model, retirement, *, cascade=False, move_children_to=None,
        child_retirements=(), child_moves=(), actor, planned_at, **options):
    """Retire an empty section, its whole subtree, or reparent all children.

    Retired sections retain their original owner: even historical sections must
    have exactly one stored contains edge. No artifact or ID is physically erased.
    All retirement guards and fresh relation identities come from the caller.
    """
    from ._document_mutations import _section_removal
    from .plans import preview_authoring_request
    owned, operations = _section_removal(model, retirement, cascade=cascade,
        move_children_to=move_children_to, child_retirements=child_retirements,
        child_moves=child_moves, actor=actor, planned_at=planned_at)
    return preview_authoring_request(owned, 'section.remove', operations,
        actor=actor, planned_at=planned_at, **options)
