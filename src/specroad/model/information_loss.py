"""Owned structural loss observations shared by migration and import.

No ID namespace, path support, acceptance policy or writer authority is shared.
"""
import json
from .canonical import canonical_json_bytes as jcs


class LossInventory:
    """Ordered detached JSON observations; interpretation belongs to each caller."""
    def __init__(self):
        self._rows = []

    def append(self, row):
        self._rows.append(jcs(row))

    @property
    def rows(self):
        return [json.loads(raw) for raw in self._rows]


def pointer_segment(name):
    return '/' + name.replace('~', '~0').replace('/', '~1')


def json_differences(before, after, pointer=''):
    """Exact JSON values, atomic ordered arrays, presence separate from null."""
    if jcs(before) == jcs(after):
        return
    if type(before) is dict and type(after) is dict:
        for key in sorted(set(before) | set(after), key=lambda s: s.encode('utf-8')):
            at = pointer + pointer_segment(key)
            if key not in before or key not in after:
                yield at, {'present': key in before, 'value': before.get(key)}, {
                    'present': key in after, 'value': after.get(key)}
            else:
                yield from json_differences(before[key], after[key], at)
    else:
        yield pointer, {'present': True, 'value': before}, {'present': True, 'value': after}
