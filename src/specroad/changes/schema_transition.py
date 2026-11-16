"""Native snapshot publication facade; all effects use the common guard."""
from .schema_transition_values import SchemaTransitionError as SchemaTransitionError

def _checkpoint(event):
    """Internal durability boundary; no data-defined callback is registered."""


def publish_schema_transition(plan, *, held_lock, backup_descriptor, authority, gates=(), merge_context=None):
    """New writes share the normal marker/receipt path, never a special journal."""
    from .snapshot_publication import publish_snapshot
    try:
        return publish_snapshot(plan,held_lock=held_lock,backup_descriptor=backup_descriptor,
            authority=authority,gates=gates,merge_context=merge_context,checkpoint=_checkpoint)
    except OSError as error:
        # An interrupted native write never implies rollback or a safe retry.
        raise SchemaTransitionError('snapshot_publication_io', exit_code=5,
                                    write_state='unknown') from error
