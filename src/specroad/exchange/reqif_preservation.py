"""Passive, bound original-source retention; no native import/export or writes.

The W assessment inventories the structure codec's uninterpreted XML only.
Mapping remainders, full native projection and attachment transport still need
their own comparisons. Its report deliberately cannot certify loss freedom.
"""
import base64
import binascii
from copy import deepcopy
from hashlib import sha256
import re

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.metadata import validate_extensions
from ..storage.json_syntax import parse_json_object
from .reqif import ReqIFError, ReqIFLimits, decode_reqif_structure
from ._reqif_values import _SEP
from ._reqif_xhtml_profile import _ATTRS, _tag

_KEY = 'specroad.reqif'
_VERSION = 'reqif-preservation-v1'
_CONTEXT = {'source_system', 'source_document', 'external_revision'}
_ENTRY = _CONTEXT | {'source_sha256', 'source_size', 'source_base64'}


def _context(value, *, code=2):
    if (type(value) is not dict or set(value) != _CONTEXT
            or any(type(value[k]) is not str or not value[k] for k in ('source_system', 'source_document'))
            or value['external_revision'] is not None and (
                type(value['external_revision']) is not str or not value['external_revision'])):
        raise ReqIFError('reqif_source_context_required', exit_code=code)
    try:
        canonical_json_bytes(value)
    except ModelError as error:
        raise ReqIFError(error.reason, exit_code=code) from error
    return dict(value)


def _hash(value, *, code=2):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ReqIFError('reqif_sha256_required', exit_code=code)
    return value


def _bound(raw, expected, *, name):
    _hash(expected)
    if type(raw) is not bytes:
        raise ReqIFError('reqif_bytes_required', exit_code=2)
    if sha256(raw).hexdigest() != expected:
        raise ReqIFError('reqif_' + name + '_changed', exit_code=6)


def _key(entry):
    return [entry[k] for k in ('source_system', 'source_document', 'external_revision', 'source_sha256')]


def _source_key(value):
    if type(value) not in (list, tuple) or len(value) != 4:
        raise ReqIFError('reqif_source_key_required', exit_code=2)
    _context(dict(zip(('source_system', 'source_document', 'external_revision'), value[:3])))
    _hash(value[3])
    return list(value)


def _entry_bytes(entry, limits):
    if type(limits) is not ReqIFLimits:
        raise ReqIFError('typed_xml_limits_required', exit_code=2)
    if type(entry) is not dict or set(entry) != _ENTRY:
        raise ReqIFError('reqif_preservation_entry_invalid')
    _context({k: entry[k] for k in _CONTEXT}, code=3)
    _hash(entry['source_sha256'], code=3)
    size, encoded = entry['source_size'], entry['source_base64']
    if type(size) is not int or size < 0 or type(encoded) is not str:
        raise ReqIFError('reqif_preservation_entry_invalid')
    # Both the claim and the encoded size are checked before decode allocates.
    if size > limits.max_bytes or len(encoded) > 4 * ((limits.max_bytes + 2) // 3):
        raise ReqIFError('xml_byte_limit', exit_code=7)
    if len(encoded) != 4 * ((size + 2) // 3):
        raise ReqIFError('reqif_preservation_size_mismatch')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ReqIFError('reqif_preservation_base64_invalid') from error
    if base64.b64encode(raw).decode('ascii') != encoded:
        raise ReqIFError('reqif_preservation_base64_noncanonical')
    if len(raw) != size or sha256(raw).hexdigest() != entry['source_sha256']:
        raise ReqIFError('reqif_preservation_integrity_mismatch')
    decode_reqif_structure(raw, limits=limits)
    return raw


def _carrier(value, limits):
    if (type(value) is not dict or set(value) != {'format_version', 'sources'}
            or value['format_version'] != _VERSION or type(value['sources']) is not list):
        raise ReqIFError('reqif_preservation_carrier_invalid')
    seen, result = set(), []
    for entry in value['sources']:
        raw = _entry_bytes(entry, limits)
        key = canonical_json_bytes(_key(entry))
        if key in seen:
            raise ReqIFError('reqif_preservation_duplicate_source')
        seen.add(key)
        result.append((entry, raw))
    return result


def merge_reqif_source(raw, *, source_context, expected_source_sha256,
                       extensions, expected_extensions_sha256, limits):
    """Return owned extension data, retaining all previous sources and keys.

    The expected extensions hash binds canonical JSON values, not a file or
    owner. A later project change still needs its normal bound Change Plan.
    """
    context = _context(source_context)
    _bound(raw, expected_source_sha256, name='source')
    decode_reqif_structure(raw, limits=limits)
    _hash(expected_extensions_sha256)
    try:
        validate_extensions(extensions)
        actual = canonical_json_sha256(extensions)
    except ModelError as error:
        raise ReqIFError(error.reason) from error
    if actual != expected_extensions_sha256:
        raise ReqIFError('reqif_extensions_changed', exit_code=6)
    entries = []
    if _KEY in extensions:
        try:
            entries = [entry for entry, _ in _carrier(extensions[_KEY], limits)]
        except ReqIFError as error:
            if error.exit_code == 3:
                raise ReqIFError('reqif_preservation_existing_conflict', exit_code=6) from error
            raise
    new = {**context, 'source_sha256': expected_source_sha256, 'source_size': len(raw),
           'source_base64': base64.b64encode(raw).decode('ascii')}
    match = next((e for e in entries if _key(e) == _key(new)), None)
    if match is not None and match != new:
        raise ReqIFError('reqif_preservation_existing_conflict', exit_code=6)
    if match is None:
        entries.append(new)
    result = deepcopy(extensions)
    result[_KEY] = {'format_version': _VERSION,
                    'sources': deepcopy(sorted(entries, key=lambda e: canonical_json_bytes(_key(e))))}
    return result


def _json_at(value, pointer):
    if (type(pointer) is not str or pointer and not pointer.startswith('/')
            or re.search(r'~(?![01])', pointer)):
        raise ReqIFError('invalid_json_pointer', exit_code=2)
    for token in pointer.split('/')[1:]:
        token = token.replace('~1', '/').replace('~0', '~')
        if type(value) is dict and token in value:
            value = value[token]
        elif type(value) is list and re.fullmatch(r'0|[1-9][0-9]*', token):
            # Compare before int conversion, including arbitrarily long tokens.
            if len(token) > len(str(len(value))) or int(token) >= len(value):
                raise ReqIFError('reqif_target_location_missing', exit_code=6)
            value = value[int(token)]
        else:
            raise ReqIFError('reqif_target_location_missing', exit_code=6)
    return value


def _target_sources(raw, expected, pointer, limits):
    _bound(raw, expected, name='target')
    try:
        extensions = _json_at(parse_json_object(raw), pointer)
        validate_extensions(extensions)
    except ReqIFError:
        raise
    except ModelError as error:
        raise ReqIFError(error.reason, pointer=error.pointer) from error
    return _carrier(extensions[_KEY], limits) if _KEY in extensions else []


def restore_reqif_source(target_bytes, *, expected_target_sha256, extensions_pointer,
                         source_key, limits):
    """Return a validated original source from an exact JSON target candidate.

    This is an original-byte roundtrip, never an export of native edits.
    """
    key = _source_key(source_key)
    entries = _target_sources(target_bytes, expected_target_sha256, extensions_pointer, limits)
    for entry, raw in entries:
        if _key(entry) == key:
            return raw
    raise ReqIFError('reqif_preservation_source_missing', exit_code=6)


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


def assess_reqif_preservation(raw, *, source_context, expected_source_sha256, direction,
                             limits, target_bytes=None, expected_target_sha256=None,
                             target_kind=None, extensions_pointer=None):
    """Assess codec-reported extras against an actual target, never claimed status.

    Missing target bytes prove no preservation. The explicit W scope excludes
    full mapping/projection and attachment transport even for identical XML.
    """
    context = _context(source_context)
    if direction not in ('import', 'export'):
        raise ReqIFError('reqif_direction_required', exit_code=2)
    _bound(raw, expected_source_sha256, name='source')
    document = decode_reqif_structure(raw, limits=limits)
    key = [context[k] for k in ('source_system', 'source_document', 'external_revision')] + [expected_source_sha256]
    preservation = None
    if target_bytes is None:
        if any(v is not None for v in (expected_target_sha256, target_kind, extensions_pointer)):
            raise ReqIFError('reqif_target_bytes_required', exit_code=2)
    elif target_kind == 'xml':
        if extensions_pointer is not None:
            raise ReqIFError('reqif_target_kind_invalid', exit_code=2)
        _bound(target_bytes, expected_target_sha256, name='target')
        decode_reqif_structure(target_bytes, limits=limits)
        if target_bytes == raw:
            preservation = {'target_sha256': expected_target_sha256,
                            'location': {'kind': 'xml', 'path': [], 'attribute': None}, 'source_key': None}
    elif target_kind == 'json':
        entries = _target_sources(target_bytes, expected_target_sha256, extensions_pointer, limits)
        for i, (entry, stored) in enumerate(entries):
            if _key(entry) == key:
                if stored != raw:
                    raise ReqIFError('reqif_preservation_source_changed', exit_code=6)
                preservation = {'target_sha256': expected_target_sha256,
                                'location': {'kind': 'json', 'pointer': extensions_pointer + '/' + _KEY + '/sources/' + str(i)},
                                'source_key': key}
    else:
        raise ReqIFError('reqif_target_kind_invalid', exit_code=2)
    items = {}
    for location, reason in _inventory(document):
        identity = {'direction': direction, 'source_sha256': expected_source_sha256,
                    'source_context': context, 'location': location, 'reason': reason}
        item_id = 'reqif-item-' + canonical_json_sha256(identity)
        item = {**identity, 'item_id': item_id, 'disposition': 'preserved' if preservation is not None else 'lost'}
        if preservation is not None:
            item['preservation_ref'] = preservation
        else:
            item['loss_id'] = item_id
        items[item_id] = item
    return deepcopy({'validation_scope': 'reqif_structure_profile_uninterpreted_xml',
                     'source_sha256': expected_source_sha256, 'source_context': context,
                     'direction': direction, 'mapping_binding': None,
                     'target_binding': None if target_bytes is None else {
                         'target_sha256': expected_target_sha256, 'kind': target_kind,
                         'extensions_pointer': extensions_pointer},
                     'assessment_complete': False, 'loss_free': False, 'native_projection_complete': False,
                     'unassessed': ['native_mapping_and_projection', 'attachment_transport'],
                     'items': [items[k] for k in sorted(items)]})
