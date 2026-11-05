"""Closed passive collection annotation shared by schema and merge readers."""
import re


def merge_annotation(node):
    """Read a closed built-in annotation; it never changes field validation."""
    rule = node['x-specroad-merge']
    if type(rule) is not dict or node.get('type') != 'array':
        raise ValueError('Invalid collection annotation')
    if rule == {'kind': 'ordered'}:
        return 'ordered', None
    if set(rule) != {'kind', 'key'} or rule['kind'] != 'set':
        raise ValueError('Invalid collection annotation')
    key = rule['key']
    if type(key) is not str or (key and not key.startswith('/')) or re.search(r'~(?![01])', key):
        raise ValueError('Invalid collection key pointer')
    return 'set', tuple(part.replace('~1', '/').replace('~0', '~') for part in key[1:].split('/')) if key else ()
