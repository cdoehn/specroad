"""Document intents translated to the common saved-plan authoring protocol.

The host supplies complete owned model/history inputs and prepared identities.
Previews allocate nothing and write nothing. Execute their saved Change Plan
through apply_authoring_plan, with fresh native checks and host authority.
This embedding API neither discovers project files nor registers a CLI writer.
"""
from ._document_operations import _creation, _contains, _move


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
    owned, operations = _move(model, section_id, parent_id=parent_id,
        relation_identity=relation_identity, position=position,
        expected_relation_sha256=expected_relation_sha256, reason=reason,
        actor=actor, planned_at=planned_at)
    return preview_authoring_request(owned, 'section.move', operations,
        actor=actor, planned_at=planned_at, **options)
