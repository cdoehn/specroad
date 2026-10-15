"""Owned content-addressed values and pure reference-retention checks.

No project access, Baseline discovery, Git provenance or write authority.
"""
from dataclasses import dataclass
from hashlib import sha256
import re

from ..model.canonical import canonical_object_bytes
from ..model.errors import ModelError


@dataclass(frozen=True)
class ObjectReference:
    sha256: str
    size: int

    def __post_init__(self):
        if type(self.sha256) is not str or re.fullmatch('[0-9a-f]{64}', self.sha256) is None:
            raise ModelError('snapshot_object_hash_required')
        if type(self.size) is not int or self.size < 0:
            raise ModelError('snapshot_object_size_required')

    @property
    def path(self):
        return 'archive/objects/' + self.sha256[:2] + '/' + self.sha256

    @property
    def data(self):
        return {'path': self.path, 'sha256': self.sha256, 'size': self.size}


@dataclass(frozen=True)
class SnapshotObject:
    """Exact content; logical role, media type and source identity belong to the manifest."""
    content: bytes

    def __post_init__(self):
        if type(self.content) is not bytes:
            raise ModelError('snapshot_object_bytes_required')

    @classmethod
    def from_json(cls, raw):
        return cls(canonical_object_bytes(raw))

    @classmethod
    def from_attachment(cls, raw):
        return cls(raw)

    @property
    def reference(self):
        return ObjectReference(sha256(self.content).hexdigest(), len(self.content))


def _reference(value):
    if type(value) is not ObjectReference:
        raise ModelError('snapshot_object_reference_required')
    return ObjectReference(value.sha256, value.size)


def _references(values):
    if type(values) not in (list, tuple):
        raise ModelError('snapshot_references_required')
    owned = {}
    for value in values:
        reference = _reference(value)
        if reference.path in owned and owned[reference.path] != reference:
            raise ModelError('snapshot_reference_conflict', path=reference.path)
        owned[reference.path] = reference
    return tuple(owned[path] for path in sorted(owned))


def _objects(values):
    if type(values) not in (list, tuple):
        raise ModelError('snapshot_objects_required')
    owned = {}
    for value in values:
        if type(value) is not SnapshotObject:
            raise ModelError('snapshot_object_required')
        value = SnapshotObject(value.content)
        path = value.reference.path
        if path in owned and owned[path].content != value.content:
            raise ModelError('snapshot_object_content_collision', path=path)
        owned[path] = value
    return owned


def check_object_retention(before, after, *, references):
    """Check actual supplied bytes and declared references; authorize no write.

    The caller supplies the complete object/reference inventory of its scope.
    This pure kernel cannot discover Baselines or prove project completeness.
    """
    left, right, retained = _objects(before), _objects(after), _references(references)
    for path in sorted(left.keys() & right.keys()):
        if left[path].content != right[path].content:
            raise ModelError('snapshot_object_replacement_forbidden', path=path)
    for reference in retained:
        if reference.path not in left:
            raise ModelError('snapshot_referenced_object_missing', path=reference.path)
        if left[reference.path].reference != reference:
            raise ModelError('snapshot_reference_conflict', path=reference.path)
        if reference.path not in right:
            raise ModelError('snapshot_referenced_object_removal', path=reference.path)
    return {'scope': 'supplied_snapshot_objects_and_references',
        'added_paths': sorted(right.keys() - left.keys()),
        'removed_paths': sorted(left.keys() - right.keys()),
        'retained_paths': sorted(left.keys() & right.keys()),
        'referenced_paths': [reference.path for reference in retained],
        'write_authorized': False, 'baseline_completeness_verified': False}
