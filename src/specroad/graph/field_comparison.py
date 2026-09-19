"""Pure JSON value comparison, not a JSON Patch or output formatter."""
from ..model.canonical import canonical_json_bytes
from .comparison_values import ComparisonResult, _owned
from ._comparison_policy import _category


def field_diff(before, after):
    """Compare exact JSON values with RFC-6901 locations. Arrays are atomic.

    Presence flags distinguish missing from explicit null. Object-key order and
    equivalent JCS number encodings are not changes. Array order IS data.
    """
    left, right = _owned(before), _owned(after)
    pending, changes = [((), True, left, True, right)], []
    while pending:
        parts, has_before, old, has_after, new = pending.pop()
        # Walk each object member once. Hashing the entire remaining subtree
        # at every level would make a deep scalar edit needlessly quadratic.
        if has_before and has_after and type(old) is dict and type(new) is dict:
            keys = sorted(set(old) | set(new), key=lambda k: k.encode('utf-8'), reverse=True)
            pending.extend((parts + (key,), key in old, old.get(key), key in new, new.get(key))
                           for key in keys)
            continue
        if has_before and has_after and canonical_json_bytes(old) == canonical_json_bytes(new):
            continue
        changes.append({'pointer': ''.join('/' + p.replace('~', '~0').replace('/', '~1') for p in parts),
            'operation': 'add' if not has_before else 'remove' if not has_after else 'replace',
            'before_present': has_before, 'after_present': has_after,
            'before': old, 'after': new, 'category': _category(parts, old, new)})
    return ComparisonResult({'comparison_version': 'field-diff-v1', 'changes': changes,
                             'changed': bool(changes)})


