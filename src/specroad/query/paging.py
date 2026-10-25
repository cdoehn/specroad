"""Exact sorting and paging of a complete supplied-inventory query selection.

This synchronous kernel keeps the selected inventory in memory. External spool
delivery, durable Work continuation and the live project/CLI adapter are separate.
"""
from dataclasses import dataclass
import json
import unicodedata

from ..model.errors import ModelError
from ..srx import MISSING
from ..srx.pointers import parse_pointer, resolve_tokens
from ._query_normalization import _sequence
from .selection import NormalizedQuery, select_query
from ._configuration_inputs import configured_sources


@dataclass(frozen=True, init=False)
class QueryPage:
    """Owned six-field result; provenance stays outside the result data object."""
    query_sha256: str
    inputs_sha256: str
    source_count: int
    _encoded: bytes
    _configuration_binding: bytes
    _evaluation_binding: bytes

    def __init__(self, selection, items, offset, limit):
        object.__setattr__(self, 'query_sha256', selection.query_sha256)
        object.__setattr__(self, 'inputs_sha256', selection.inputs_sha256)
        object.__setattr__(self, 'source_count', selection.source_count)
        object.__setattr__(self, '_configuration_binding', selection._configuration_binding)
        object.__setattr__(self, '_evaluation_binding', selection._evaluation_binding)
        data = {'items': items, 'total': selection.total, 'offset': offset,
                'limit': limit, 'returned': len(items),
                'truncated': offset + len(items) < selection.total}
        # Keep projection keys in requested order and preserve original strings.
        object.__setattr__(self, '_encoded', json.dumps(data, ensure_ascii=False,
                                                       allow_nan=False).encode('utf-8'))

    @property
    def data(self):
        return json.loads(self._encoded)

    @property
    def validation_scope(self):
        return 'supplied_query_inventory_only'

    @property
    def configuration_binding(self):
        return json.loads(self._configuration_binding)

    @property
    def evaluation_binding(self):
        return json.loads(self._evaluation_binding)


def _scalar_key(value, pointer):
    if value is MISSING:
        return (0,)
    if value is None:
        return (1,)
    if type(value) is bool:
        return (2, value)
    if type(value) in (int, float):
        return (3, value)
    if type(value) is str:
        return (4, unicodedata.normalize('NFC', value).encode('utf-8'))
    raise ModelError('query_sort_value_not_scalar', pointer=pointer)


def query_records(records, query, *, project, configuration=None, configuration_id=None, verification=None,
                  partial=None):
    """Filter all supplied sources, sort all matches, then form the exact page.

    Sort values come from original fields, independently of projection. All
    selected values are checked before pagination, including for limit zero.
    No implicit I/O, cache, source rewrite or hidden result-count cap is used.
    """
    if type(query) is not NormalizedQuery:
        raise ModelError('normalized_query_required')
    records = tuple(_sequence(records))
    records = configured_sources(records, configuration_id)
    data = query.data
    ordering = []
    for index, item in enumerate(data['sort']):
        pointer = '/sort/' + str(index)
        key = item['key']
        tokens = parse_pointer(key, rule_id='query-sort', at=pointer + '/key') if key.startswith('/') else (key,)
        if verification is None and tokens and tokens[0] == 'verification_result':
            raise ModelError('query_verification_provider_required', pointer=pointer)
        ordering.append((tokens, item['direction'] == 'desc', pointer))
    selection = select_query(records, query, project=project, configuration=configuration,
                             configuration_id=configuration_id, verification=verification, partial=partial)
    from ..verification._read_evaluation import selected_artifacts
    artifacts = selected_artifacts(records, selection.artifact_ids, verification)
    rows = []
    for item in selection.items:
        artifact = artifacts[item['id']]
        keys = tuple(_scalar_key(resolve_tokens(artifact, tokens, rule_id='query-sort',
                                                at=pointer + '/key'), pointer)
                     for tokens, _, pointer in ordering)
        rows.append((item, keys))
    # Stable sorting preserves the final ascending ID tie-breaker even when
    # preceding keys use descending directions.
    rows.sort(key=lambda row: row[0]['id'])
    for index in reversed(range(len(ordering))):
        rows.sort(key=lambda row: row[1][index], reverse=ordering[index][1])
    offset, limit = data['offset'], data['limit']
    items = [row[0] for row in rows[offset:offset + limit]]
    return QueryPage(selection, items, offset, limit)
