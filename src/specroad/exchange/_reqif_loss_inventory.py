"""Source locations and machine reasons for bound ReqIF loss assessment.

Inventory operates on decoded source data and explicit mapping comparisons.
It does not format messages, choose a preservation proof, or authorize writes.
"""
from ..model.canonical import canonical_json_bytes
from ._reqif_fields import records
from ._reqif_values import _SEP
from ._reqif_xhtml_profile import _ATTRS, _tag


def _pointer(parent, key):
    return parent + '/' + str(key).replace('~', '~0').replace('/', '~1')



def _location(path, attribute=None):
    return {'kind': 'xml', 'path': list(path), 'attribute': attribute}



def _nodes(document):
    result, pending = [], [(document._root, ())]
    while pending:
        node, path = pending.pop()
        result.append((node, path))
        pending.extend(reversed([(c, path + (i,)) for i, c in enumerate(node.children)]))
    return result



def _attribute(key):
    namespace, _, name = key.rpartition(_SEP)
    return {'namespace': namespace, 'name': name}



def _inventory(document):
    nodes, attrs = {}, {}
    pending = [(document._root, [])]
    while pending:
        node, path = pending.pop()
        nodes[node.pointer] = (node, path)
        for key, _ in node.attributes:
            namespace, _, name = key.rpartition(_SEP)
            attrs[node.pointer + '/@' + key] = {
                'kind': 'xml', 'path': path, 'attribute': {'namespace': namespace, 'name': name}}
        pending.extend((child, path + [i]) for i, child in enumerate(node.children))
    items = []
    for pointer, reason in document.unsupported:
        if pointer in attrs:
            items.append((attrs[pointer], reason))
        else:
            node, path = nodes[pointer]
            if reason == 'reqif_xhtml_attribute_not_representable':
                for key, _ in node.attributes:
                    if key not in _ATTRS.get(_tag(node), set()):
                        items.append((attrs[node.pointer + '/@' + key], reason))
            else:
                items.append(({'kind': 'xml', 'path': path, 'attribute': None}, reason))
    # An opaque subtree is one unit; independent attributes on partially mapped
    # elements remain individual units. Different reasons at one place survive.
    opaque = [loc['path'] for loc, _ in items if loc['attribute'] is None]
    return [(loc, reason) for loc, reason in items if not any(
        (len(parent) < len(loc['path']) or parent == loc['path'] and loc['attribute'] is not None)
        and loc['path'][:len(parent)] == parent for parent in opaque)]



def _xml_inventory(document, projections, consumed, mapping):
    indexed = _nodes(document)
    paths = {id(node): path for node, path in indexed}
    opaque, attribute_reasons, value_uses, skip = {}, {}, {}, set()
    for location, reason in _inventory(document):
        path = tuple(location['path'])
        if location['attribute'] is None:
            opaque.setdefault(path, set()).add(reason)
        else:
            attribute_reasons[(path, canonical_json_bytes(location['attribute']))] = reason
    for node, path in indexed:
        if node.tag == 'THE-ORIGINAL-VALUE':
            opaque.setdefault(path, set()).add('reqif_xhtml_original_not_projected')
    rows = [] if mapping is None else mapping.resource.data['fields']
    for record in records(document):
        definitions = next(t.definitions for t in document.types if t.identifier == record.type_id)
        explicit = {v.definition_id: v for v in record.values}
        reasons = {v['definition_id']: v['reason'] for v in projections[record.identifier]['unrepresentable']}
        for definition in definitions:
            value = explicit.get(definition.identifier, definition.default)
            if value is None:
                continue
            path = paths[id(value.element)]
            used = (record.identifier, definition.identifier) in consumed
            reason = reasons.get(definition.identifier)
            if reason is None and not used:
                mapped = any(r['external_type'] == record.type_id and r['external_field'] == definition.identifier for r in rows)
                reason = 'reqif_mapping_target_mismatch' if mapped else 'reqif_mapping_remainder'
            value_uses.setdefault(path, []).append((value, reason))
    for path, uses in value_uses.items():
        reasons = {reason for _, reason in uses if reason is not None}
        if reasons:
            opaque.setdefault(path, set()).update(reasons)
        else:
            value = uses[0][0]
            # The field comparison proves the effective value, not unrelated
            # metadata, original XHTML, editable flags or foreign attributes.
            skip.add((path, 'THE-VALUE'))
            for i, child in enumerate(value.element.children):
                if child.tag in ('DEFINITION', 'VALUES', 'THE-VALUE'):
                    skip.add((path + (i,), None))
    result = []
    for node, path in indexed:
        if any(path[:size] in opaque for size in range(len(path))):
            continue
        if path in opaque:
            result.extend((_location(path), reason) for reason in sorted(opaque[path]))
            continue
        # Native value comparison cannot consume foreign attributes even in
        # an otherwise mapped reference/value subtree.
        for name, _ in node.attributes:
            attr = _attribute(name)
            reason = attribute_reasons.get((path, canonical_json_bytes(attr)))
            if reason is not None:
                result.append((_location(path, attr), reason))
        if any((path[:size], None) in skip for size in range(len(path) + 1)):
            continue
        for name, _ in node.attributes:
            if (path, name) not in skip:
                attr = _attribute(name)
                result.append((_location(path, attr), attribute_reasons.get((path, canonical_json_bytes(attr)), 'reqif_metadata_not_projected')))
        # Nonempty text and empty leaf elements carry independent information;
        # container whitespace is formatting, already retained in source bytes.
        if not node.children:
            result.append((_location(path), 'reqif_xml_content_not_projected'))
        elif any(type(c) is str and c.strip() for c in node.content):
            result.append((_location(path), 'reqif_xml_mixed_content_not_projected'))
    return result



def _native_inventory(value, consumed):
    result = []
    for name, content in value.items():
        if name in consumed or name == 'attachments':
            continue
        at = _pointer('', name)
        if name == 'extensions' and type(content) is dict and content:
            result.extend(({'kind': 'json', 'pointer': _pointer(at, key)}, 'reqif_native_extension_not_projected') for key in content)
        elif name == 'relations' and type(content) is list and content:
            result.extend(({'kind': 'json', 'pointer': _pointer(at, i)}, 'reqif_native_relation_not_projected') for i in range(len(content)))
        else:
            result.append(({'kind': 'json', 'pointer': at}, 'reqif_native_field_not_projected'))
    return result
