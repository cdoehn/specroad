"""Pure replacement guards, independent of storage and graph indices."""

from ..model.errors import ModelError
from ._relation_validation import KEY_FIELDS, _json_data
from .relation_values import Relation, SourceRelations

def require_relation_keys_unchanged(previous, proposed):
    """Check one retained edge; no update, lifecycle gate or write is performed."""
    if type(previous) is not Relation or type(proposed) is not Relation:
        raise ModelError("relation_value_required")
    if previous.source != proposed.source:
        raise ModelError("relation_source_immutable")
    old, new = previous.data, proposed.data
    for name in KEY_FIELDS:
        if old[name] != new[name]:
            raise ModelError("relation_key_immutable", pointer="/" + name)


def prepare_relation_update(previous, changes):
    """Return checked replacement metadata. Never edits the source artifact.

    Identical key repetitions are harmless no-ops; changed keys are rejected.
    Removing a relation and adding a fresh identity is a different operation
    and belongs to future authoring/transaction planning, not this helper.
    """
    if type(previous) is not Relation:
        raise ModelError("relation_value_required")
    if type(changes) is not dict:
        raise ModelError("relation_changes_object_required")
    _json_data(changes)
    data = previous.data
    for name in KEY_FIELDS:
        if name in changes and changes[name] != data[name]:
            raise ModelError("relation_key_immutable", pointer="/" + name)
    data.update(changes)
    proposed = Relation(previous.source, data)
    require_relation_keys_unchanged(previous, proposed)
    return proposed


def require_retained_relation_keys_unchanged(previous, proposed):
    """Check shared relation IDs when comparing two source artifact revisions.

    Reordering is allowed. Additions/removals remain distinct operations, not
    implicit update permissions. Allocation and lifecycle validation are later.
    """
    if type(previous) is not SourceRelations or type(proposed) is not SourceRelations:
        raise ModelError("source_relations_required")
    if previous.identity != proposed.identity:
        raise ModelError("relation_source_immutable")
    old = {relation.identity.id: relation for relation in previous.relations}
    for index, relation in enumerate(proposed.relations):
        if relation.identity.id in old:
            try:
                require_relation_keys_unchanged(old[relation.identity.id], relation)
            except ModelError as error:
                error.path = proposed.path
                error.pointer = "/relations/" + str(index) + error.pointer
                raise
