"""Immutable scope-v1 selectors, not a query evaluator or a scope closure.

Query envelopes use the internal normalized-query contract below. They contain
values, never filenames to load. Actual query execution belongs to its resolver.
"""
from dataclasses import dataclass
import json
import re
import unicodedata

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.artifact_types import artifact_types
from ._relation_validation import _reference

_FIELDS = frozenset(('scope_version', 'scope_kind', 'selector', 'configuration_id',
                     'closure_profile', 'boundary_policy'))
_KINDS = frozenset(('specification', 'project', 'release', 'document', 'query', 'explicit'))
_FILTERS = frozenset(('type', 'maturity', 'implementation_status', 'verification_plan_status',
                     'verification_result', 'owner', 'tag', 'release', 'has_relation',
                     'missing_relation', 'full_text'))
_SORT_KEYS = frozenset(('artifact_type', 'id', 'title', 'maturity', 'revision', 'owner',
                       'implementation_status', 'verification_plan_status', 'verification_result'))


def _text(value):
    if type(value) is not str or not value.strip() or '\0' in value:
        raise ModelError('invalid_scope_identity')
    try:
        value.encode('utf-8')
    except UnicodeError as error:
        raise ModelError('invalid_scope_identity') from error
    return value


def _artifact_id(value, kind=None):
    _reference(value)
    if kind is not None:
        prefix = next(item.prefix for item in artifact_types() if item.artifact_type == kind)
        if value.split('-')[1] != prefix:
            raise ModelError('scope_selector_type_mismatch')
    return value


def _ordered_ids(value, *, artifacts=False):
    if type(value) is not list:
        raise ModelError('scope_identity_array_required')
    for item in value:
        (_artifact_id if artifacts else _text)(item)
    if len(set(value)) != len(value):
        raise ModelError('duplicate_scope_identity')
    if value != sorted(value, key=lambda item: item.encode('utf-8')):
        raise ModelError('noncanonical_scope_selector')


def _pointer(value):
    if type(value) is not str or (value and not value.startswith('/')) or re.search(r'~(?![01])', value):
        raise ModelError('invalid_scope_query_pointer')


def _query(value):
    """Check a fully materialized internal envelope; no execution or defaults.

    Filters are OR within each group, SRX filters are separate AND operands.
    Their semantic/type validation and evaluation are later query-engine duties.
    This layer binds their complete canonical values and rejects file pointers.
    """
    keys = {'filters', 'srx_filters', 'select', 'sort', 'evaluation', 'offset', 'limit'}
    if type(value) is not dict or set(value) != keys:
        raise ModelError('normalized_scope_query_required')
    for name in ('offset', 'limit'):
        if type(value[name]) is not int or value[name] < 0:
            raise ModelError('invalid_scope_query_pagination')
    if type(value['filters']) is not dict or set(value['filters']) - _FILTERS:
        raise ModelError('unknown_scope_query_filter')
    for name, values in value['filters'].items():
        _ordered_ids(values)
        if name == 'full_text' and any(v != unicodedata.normalize('NFC', v).casefold() for v in values):
            raise ModelError('nonnormalized_scope_full_text')
    if type(value['srx_filters']) is not list:
        raise ModelError('invalid_scope_query_expressions')
    for operand in value['srx_filters']:
        if (type(operand) is not dict or set(operand) != {'expression', 'sha256'}
                or type(operand['expression']) is not dict
                or operand['sha256'] != canonical_json_sha256(operand['expression'])):
            raise ModelError('invalid_scope_query_expression_binding')
    if type(value['select']) is not list:
        raise ModelError('invalid_scope_query_projection')
    for pointer in value['select']:
        _pointer(pointer)
    if len(set(value['select'])) != len(value['select']):
        raise ModelError('duplicate_scope_query_projection')
    if type(value['sort']) is not list or not value['sort']:
        raise ModelError('materialized_scope_query_sort_required')
    seen = set()
    for item in value['sort']:
        if type(item) is not dict or set(item) != {'key', 'direction'}:
            raise ModelError('invalid_scope_query_sort')
        key = _text(item['key'])
        if key not in _SORT_KEYS:
            _pointer(key)
        if item['direction'] not in ('asc', 'desc') or key in seen:
            raise ModelError('invalid_scope_query_sort')
        seen.add(key)
    if value['evaluation'] is not None and type(value['evaluation']) is not dict:
        raise ModelError('scope_query_evaluation_content_required')


def _descriptor(value):
    # Canonical validation happens first: no foreign conversion hooks, non-finite
    # numbers, cyclic containers, or invalid Unicode are admitted to selectors.
    canonical_json_bytes(value)
    if (type(value) is not dict or set(value) != _FIELDS
            or value['scope_version'] != 'scope-v1'
            or value['closure_profile'] != 'core-closure-v1'
            or value['boundary_policy'] not in ('closed', 'partial')
            or type(value['scope_kind']) is not str or value['scope_kind'] not in _KINDS):
        raise ModelError('invalid_scope_descriptor')
    if value['configuration_id'] is not None:
        _artifact_id(value['configuration_id'], 'configuration')
    kind, selector = value['scope_kind'], value['selector']
    if type(selector) is not dict:
        raise ModelError('invalid_scope_selector')
    fields = {'release': {'release_id'}, 'document': {'document_id'},
              'query': {'query'}, 'explicit': {'artifact_ids', 'resource_ids'}}
    if set(selector) != fields.get(kind, set()):
        raise ModelError('invalid_scope_selector')
    if kind in ('release', 'document'):
        _artifact_id(selector[kind + '_id'], kind)
    elif kind == 'explicit':
        _ordered_ids(selector['artifact_ids'], artifacts=True)
        _ordered_ids(selector['resource_ids'])
    elif kind == 'query':
        _query(selector['query'])


@dataclass(frozen=True, init=False)
class ScopeDescriptor:
    """Validated selector shape. It does not claim full query/model validity."""
    _encoded: bytes

    def __init__(self, value):
        _descriptor(value)
        object.__setattr__(self, '_encoded', canonical_json_bytes(value))

    @property
    def data(self):
        return json.loads(self._encoded)

    @property
    def canonical_bytes(self):
        return self._encoded

    @property
    def sha256(self):
        return canonical_json_sha256(self.data)

    @property
    def scope_kind(self):
        return self.data['scope_kind']

    @property
    def validation_scope(self):
        return 'scope_selector_shape_only'
