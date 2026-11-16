"""Compatibility adapter to the complete shared snapshot publication path."""
from .snapshot_publication import publish_snapshot
from .receipt_values import transaction_receipt_path
from .write_guard_values import validate_transaction, completion
from ._guarded_io import _read_path


def publish_guarded_snapshot(plan, *, held_lock, backup_descriptor, authority, gates=(), merge_context=None):
    from . import guarded_write
    publish_snapshot(plan,held_lock=held_lock,backup_descriptor=backup_descriptor,
        authority=authority,gates=gates,merge_context=merge_context,checkpoint=guarded_write._checkpoint)
    raw=_read_path(held_lock._files,transaction_receipt_path(held_lock.record.data['transaction_id']))
    return completion(validate_transaction(raw),current=True)
