"""Pure JSON field merging, before identity, metadata and target-validation gates.

The caller supplies three present JSON values of the same logical resource.
Missing object members are distinct from JSON null; a missing RESOURCE is not
an input to this function. Results neither change the source inventory nor
authorize deletion/publication. Concurrent arrays await schema-aware merging.
"""
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


def _kind(value):
    if value is _MISSING:
        return 'missing'
    if value is None:
        return 'null'
    return {bool: 'boolean', int: 'number', float: 'number', str: 'string',
            dict: 'object', list: 'array'}[type(value)]


def _conflict_kind(base, ours, theirs):
    old, left, right = (_kind(value) for value in (base, ours, theirs))
    if 'missing' in (left, right):
        return 'remove_edit'
    if left != right or (left in ('object', 'array') and old not in ('missing', left)):
        return 'type_change'
    if left == 'array':
        return 'collection_semantics_required'
    return 'scalar_change'


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

    holder = {}
    pending = [(*values, '', holder, 'value')]
    while pending:
        old, left, right, pointer, parent, name = pending.pop()
        if type(left) is dict and type(right) is dict and (old is _MISSING or type(old) is dict):
            before = {} if old is _MISSING else old
            result = {}; parent[name] = result
            keys = sorted(set(before) | set(left) | set(right), key=lambda key: key.encode('utf-8'), reverse=True)
            for key in keys:
                child = pointer + '/' + key.replace('~', '~0').replace('/', '~1')
                pending.append((before.get(key, _MISSING), left.get(key, _MISSING),
                                right.get(key, _MISSING), child, result, key))
            continue
        if _equal(left, right):
            target = left
        elif _equal(old, left):
            target = right
        elif _equal(old, right):
            target = left
        else:
            kind = _conflict_kind(old, left, right)
            conflicts.append(FieldConflict(pointer, kind, *(FieldValue._create(value) for value in (old, left, right))))
            continue
        if target is not _MISSING:
            parent[name] = target
    return FieldMergeResult._create(holder.get('value', _MISSING), conflicts)
