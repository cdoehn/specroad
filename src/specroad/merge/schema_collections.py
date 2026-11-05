"""Explicit built-in collection rules, never field-name or element heuristics."""
from ..model.merge_annotations import merge_annotation
from ..model.canonical import canonical_json_bytes as jcs
from ..model.errors import ModelError
from .field_values import _MISSING


def collection_rules(schema):
    rules = {}
    pending = [(schema, (), False)]
    while pending:
        node, path, conditional = pending.pop()
        if type(node) is bool:
            continue
        if 'x-specroad-merge' in node:
            if conditional:
                raise ValueError('Conditional collection annotations are unsupported')
            kind, key = merge_annotation(node)
            rule = key if kind == 'set' else None
            if path in rules and rules[path] != rule:
                raise ValueError('Conflicting built-in collection annotations')
            rules[path] = rule
        if '$ref' in node:
            name = node['$ref'][len('#/$defs/'):].replace('~1', '/').replace('~0', '~')
            pending.append((schema['$defs'][name], path, conditional))
        for key, child in node.get('properties', {}).items():
            pending.append((child, path+(key,), conditional))
        if 'items' in node:
            pending.append((node['items'], path+(None,), conditional))
        pending.extend((child, path, conditional) for child in node.get('allOf', ()))
        pending.extend((child, path, True) for child in node.get('anyOf', ()))
        for key in ('not', 'additionalProperties', 'propertyNames'):
            if key in node:
                pending.append((node[key], path, True))
    return rules


def element_key(item, key, pointer):
    value = item
    for member in key:
        if type(value) is not dict or member not in value:
            raise ModelError('merge_set_key', pointer=pointer)
        value = value[member]
    if type(value) in (dict, list):
        raise ModelError('merge_set_key', pointer=pointer)
    return jcs(value), value


def set_map(value, key, pointer):
    result = {}
    if value is not _MISSING:
        for item in value:
            token, _ = element_key(item, key, pointer)
            if token in result:
                raise ModelError('duplicate_merge_set_key', pointer=pointer)
            result[token] = item
    return result


def check_collections(value, rules):
    """Check every source before shortcuts, including nested unchanged sets."""
    pending = [(value, (), '')]
    while pending:
        item, path, pointer = pending.pop()
        key = rules.get(path)
        if key is not None and type(item) is list:
            set_map(item, key, pointer)
        if type(item) is dict:
            pending.extend((child, path+(name,), pointer+'/'+name.replace('~', '~0').replace('/', '~1'))
                           for name, child in item.items())
        elif type(item) is list:
            pending.extend((child, path+(None,), pointer+'/'+str(index)) for index, child in enumerate(item))


def same_value(left, right, path, rules):
    """Set order is immaterial; ordinary arrays retain their exact JSON order."""
    pending = [(left, right, path)]
    while pending:
        left, right, path = pending.pop()
        if left is _MISSING or right is _MISSING:
            if left is not right:
                return False
        elif type(left) is dict and type(right) is dict:
            if left.keys() != right.keys():
                return False
            pending.extend((left[key], right[key], path+(key,)) for key in left)
        elif type(left) is list and type(right) is list and rules.get(path) is not None:
            key = rules[path]
            lmap, rmap = set_map(left, key, ''), set_map(right, key, '')
            if lmap.keys() != rmap.keys():
                return False
            pending.extend((lmap[key], rmap[key], path+(None,)) for key in lmap)
        elif jcs(left) != jcs(right):
            return False
    return True
