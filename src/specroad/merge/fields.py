"""Pure JSON field merging, before identity, metadata and target-validation gates.

The caller supplies three present JSON values of the same logical resource.
Missing object members are distinct from JSON null; a missing RESOURCE is not
an input to this function. Results neither change the source inventory nor
authorize deletion/publication. Concurrent arrays await schema-aware merging.
"""
from dataclasses import dataclass
import json

from ..model.canonical import canonical_json_bytes as jcs
from ..model.errors import ModelError


_MISSING = object()


@dataclass(frozen=True, init=False, eq=False)
class FieldValue:
    """Owned observation of a member, including its explicit absence."""
    _encoded: bytes | None

    @classmethod
    def _create(cls, value):
        result = object.__new__(cls)
        object.__setattr__(result, '_encoded', None if value is _MISSING else jcs(value))
        return result

    @property
    def present(self):
        return self._encoded is not None

    @property
    def value(self):
        if not self.present:
            raise ModelError('merge_field_missing')
        try:
            return json.loads(self._encoded)
        except (ValueError, RecursionError) as error:
            raise ModelError('unsupported_json_nesting') from error

    def __bool__(self):
        raise TypeError('Use the explicit presence of a field observation')


@dataclass(frozen=True)
class FieldConflict:
    """Internal field observation, not a persisted, resolved merge-plan conflict."""
    pointer: str
    kind: str
    base: FieldValue
    ours: FieldValue
    theirs: FieldValue


@dataclass(frozen=True, init=False, eq=False)
class FieldMergeResult:
    _target: FieldValue
    conflicts: tuple

    @classmethod
    def _create(cls, value, conflicts):
        result = object.__new__(cls)
        object.__setattr__(result, 'conflicts', tuple(conflicts))
        object.__setattr__(result, '_target', FieldValue._create(_MISSING if conflicts else value))
        return result

    @property
    def merged(self):
        return not self.conflicts

    @property
    def value(self):
        if self.conflicts:
            raise ModelError('unresolved_field_merge')
        return self._target.value

    @property
    def ready(self):
        return False

    @property
    def write_authorized(self):
        return False

    def __bool__(self):
        raise TypeError('A field merge is not a validated merge plan or write authority')


def _equal(left, right):
    if left is _MISSING or right is _MISSING:
        return left is right
    return jcs(left) == jcs(right)


def merge_fields(base, ours, theirs):
    """Recursively combine independent fields and JSON-equivalent target values.

    No profile or lifecycle decision is implied. Even a conflict-free value
    still requires the later resource/history, invariant and writer gates.
    """
    # Validate and detach ALL inputs, even a side an equality shortcut ignores.
    values = [FieldValue._create(value).value for value in (base, ours, theirs)]
    conflicts = []

    def visit(old, left, right, pointer):
        if type(left) is dict and type(right) is dict and (old is _MISSING or type(old) is dict):
            before = {} if old is _MISSING else old
            result = {}
            for key in sorted(set(before) | set(left) | set(right), key=lambda key: key.encode('utf-8')):
                child = pointer + '/' + key.replace('~', '~0').replace('/', '~1')
                value = visit(before.get(key, _MISSING), left.get(key, _MISSING), right.get(key, _MISSING), child)
                if value is not _MISSING:
                    result[key] = value
            return result
        if _equal(left, right):
            return left
        if _equal(old, left):
            return right
        if _equal(old, right):
            return left
        kind = 'collection_semantics_required' if type(left) is list and type(right) is list else 'concurrent_change'
        conflicts.append(FieldConflict(pointer, kind, *(FieldValue._create(value) for value in (old, left, right))))
        return _MISSING

    try:
        target = visit(*values, '')
    except RecursionError as error:
        raise ModelError('unsupported_json_nesting') from error
    return FieldMergeResult._create(target, conflicts)
