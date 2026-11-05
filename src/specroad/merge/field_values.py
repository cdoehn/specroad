"""Immutable field observations; missing is not JSON null or write authority."""
from dataclasses import dataclass

from ..model.canonical import canonical_json_bytes as jcs
from ..model.errors import ModelError


_MISSING = object()


def _freeze(value):
    # The shared canonical boundary rejects foreign types/hooks, cycles, bad
    # Unicode and lossy numbers. The owned tree keeps deep values off the call
    # stack and never retains a caller's mutable container.
    jcs(value)
    pending, built = [('visit', value)], []
    while pending:
        action, item = pending.pop()
        if action == 'finish':
            kind, keys, count = item
            children = built[-count:] if count else []
            if count:
                del built[-count:]
            built.append((kind, tuple(zip(keys, children)) if kind == 'object' else tuple(children)))
        elif type(item) in (list, dict):
            keys = tuple(item) if type(item) is dict else ()
            children = tuple(item[key] for key in keys) if type(item) is dict else tuple(item)
            pending.append(('finish', ('object' if type(item) is dict else 'array', keys, len(children))))
            pending.extend(('visit', child) for child in reversed(children))
        else:
            built.append(('scalar', item))
    return built[0]


def _thaw(tree):
    holder = [None]
    pending = [(tree, holder, 0)]
    while pending:
        (kind, contents), parent, key = pending.pop()
        if kind == 'object':
            value = dict.fromkeys(name for name, _ in contents)
            pending.extend((child, value, name) for name, child in reversed(contents))
        elif kind == 'array':
            value = [None] * len(contents)
            pending.extend((child, value, index) for index, child in reversed(tuple(enumerate(contents))))
        else:
            value = contents
        parent[key] = value
    return holder[0]


@dataclass(frozen=True, init=False, eq=False)
class FieldValue:
    """Owned observation of a member, including its explicit absence."""
    _tree: tuple | None

    @classmethod
    def _create(cls, value):
        result = object.__new__(cls)
        object.__setattr__(result, '_tree', None if value is _MISSING else _freeze(value))
        return result

    @property
    def present(self):
        return self._tree is not None

    @property
    def value(self):
        if not self.present:
            raise ModelError('merge_field_missing')
        return _thaw(self._tree)

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


@dataclass(frozen=True)
class CollectionConflict(FieldConflict):
    """Whole-array observations with stable keys, never a fictitious shared index."""
    element_keys: tuple


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
