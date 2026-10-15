"""Content-addressed snapshot bytes, independent of Baseline and Git metadata."""
from .objects import ObjectReference, SnapshotObject, SnapshotObjectStore, read_snapshot_object

__all__ = ['ObjectReference', 'SnapshotObject', 'SnapshotObjectStore', 'read_snapshot_object']
