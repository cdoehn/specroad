"""Pure recurrence and conflict construction over already-owned JSON values."""
from ..model.canonical import canonical_json_bytes as jcs
from .field_values import _MISSING, FieldConflict, FieldValue


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


def _equal(left, right):
    if left is _MISSING or right is _MISSING:
        return left is right
    return jcs(left) == jcs(right)


def _conflict(pointer, base, ours, theirs):
    return FieldConflict(pointer, _conflict_kind(base, ours, theirs),
                         *(FieldValue._create(value) for value in (base, ours, theirs)))


def merge_owned(base, ours, theirs):
    """Return a candidate and every conflict; callers must withhold conflicted targets."""
    conflicts = []
    holder = {}
    pending = [(base, ours, theirs, '', holder, 'value')]
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
            conflicts.append(_conflict(pointer, old, left, right))
            continue
        if target is not _MISSING:
            parent[name] = target
    return holder.get('value', _MISSING), tuple(conflicts)
