"""Pure recurrence and conflict construction over already-owned JSON values."""
from ..model.canonical import canonical_json_bytes as jcs
from .field_values import _MISSING, CollectionConflict, FieldConflict, FieldValue
from .schema_collections import element_key, same_value, set_map


def _kind(value):
    if value is _MISSING:
        return 'missing'
    if value is None:
        return 'null'
    return {bool: 'boolean', int: 'number', float: 'number', str: 'string',
            dict: 'object', list: 'array'}[type(value)]


def _conflict_kind(base, ours, theirs, schema_aware=False):
    old, left, right = (_kind(value) for value in (base, ours, theirs))
    if 'missing' in (left, right):
        return 'remove_edit'
    if left != right or (left in ('object', 'array') and old not in ('missing', left)):
        return 'type_change'
    if left == 'array':
        return 'ordered_sequence_change' if schema_aware else 'collection_semantics_required'
    return 'scalar_change'


def _equal(left, right):
    if left is _MISSING or right is _MISSING:
        return left is right
    return jcs(left) == jcs(right)


def _conflict(pointer, base, ours, theirs, schema_aware=False):
    return FieldConflict(pointer, _conflict_kind(base, ours, theirs, schema_aware),
                         *(FieldValue._create(value) for value in (base, ours, theirs)))


def merge_owned(base, ours, theirs, rules=None):
    """Return a candidate and every conflict; callers withhold conflicted targets."""
    conflicts, holder = [], {}
    pending = [('visit', (base, ours, theirs, '', (), holder, 'value', conflicts))]
    while pending:
        action, task = pending.pop()
        if action == 'finish_set':
            old, left, right, pointer, parent, name, reports, cells = task
            failures = [cell for cell in cells if cell[2]]
            if failures:
                reports.append(CollectionConflict(pointer, 'set_element_conflict',
                    *(FieldValue._create(value) for value in (old, left, right)),
                    tuple(FieldValue._create(cell[0]) for cell in failures)))
            else:
                parent[name] = [cell[1]['value'] for cell in cells if 'value' in cell[1]]
            continue
        old, left, right, pointer, path, parent, name, reports = task
        key = None if rules is None else rules.get(path)
        if key is not None and type(left) is list and type(right) is list and (old is _MISSING or type(old) is list):
            if same_value(left, right, path, rules):
                parent[name] = left
            elif same_value(old, left, path, rules):
                parent[name] = right
            elif same_value(old, right, path, rules):
                parent[name] = left
            else:
                before, lmap, rmap = (set_map(value, key, pointer) for value in (old, left, right))
                cells, children = [], []
                for token in sorted(set(before) | set(lmap) | set(rmap)):
                    values = tuple(mapping.get(token, _MISSING) for mapping in (before, lmap, rmap))
                    _, identity = element_key(next(value for value in values if value is not _MISSING), key, pointer)
                    cell, failures = {}, []
                    cells.append((identity, cell, failures))
                    children.append(('visit', (*values, pointer, path+(None,), cell, 'value', failures)))
                pending.append(('finish_set', (old, left, right, pointer, parent, name, reports, cells)))
                pending.extend(reversed(children))
            continue
        if type(left) is dict and type(right) is dict and (old is _MISSING or type(old) is dict):
            before = {} if old is _MISSING else old
            result = {}; parent[name] = result
            keys = sorted(set(before) | set(left) | set(right), key=lambda key: key.encode('utf-8'), reverse=True)
            for member in keys:
                child = pointer + '/' + member.replace('~', '~0').replace('/', '~1')
                pending.append(('visit', (before.get(member, _MISSING), left.get(member, _MISSING),
                    right.get(member, _MISSING), child, path+(member,), result, member, reports)))
            continue
        equal = _equal if rules is None else lambda a, b: same_value(a, b, path, rules)
        if equal(left, right):
            target = left
        elif equal(old, left):
            target = right
        elif equal(old, right):
            target = left
        else:
            reports.append(_conflict(pointer, old, left, right, rules is not None))
            continue
        if target is not _MISSING:
            parent[name] = target
    return holder.get('value', _MISSING), tuple(conflicts)
