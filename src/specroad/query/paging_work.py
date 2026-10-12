"""Live M6 sorting and page delivery over an owned supplied-input selection.

Selection still materializes its input and matches. Sorting uses bounded runs;
advance performs real sort/delivery work, not replay of a precomputed page.
This is a process-local capability, not a durable Work checkpoint or CLI adapter.
"""
from dataclasses import dataclass
from functools import total_ordering
import json

from ..diagnostics.spooling import DiagnosticSort, DiagnosticSpool
from ..model.errors import ModelError
from ..result_contract import ResultContractError
from ..security.errors import SafetyViolation
from ..srx import MISSING
from ..srx.pointers import parse_pointer, resolve_tokens
from ..storage._spool_segments import _positive
from ._query_normalization import _sequence
from .paging import QueryPage, _scalar_key
from .selection import NormalizedQuery, select_query


@total_ordering
@dataclass(frozen=True)
class _Descending:
    value: tuple

    def __lt__(self, other):
        if type(other) is not _Descending:
            return NotImplemented
        return self.value > other.value


@dataclass(frozen=True, init=False)
class _QueryRow:
    _item_json: str
    _values: tuple
    _descending: tuple

    def __init__(self, item, values, descending):
        if (type(item) is not dict or type(item.get('id')) is not str
                or type(item.get('artifact_type')) is not str
                or type(values) is not tuple or type(descending) is not tuple
                or len(values) != len(descending)
                or any(type(value) is not bool for value in descending)):
            raise ResultContractError('An owned query row and exact sort directions are required')
        for index, value in enumerate(values):
            _scalar_key(value, '/sort/' + str(index))
        # The outer M6 JSON codec sorts object keys. Encode the projection as
        # text so its requested pointer order survives every external merge.
        encoded = json.dumps(item, ensure_ascii=False, allow_nan=False)
        object.__setattr__(self, '_item_json', encoded)
        object.__setattr__(self, '_values', values)
        object.__setattr__(self, '_descending', descending)

    @property
    def item(self):
        return json.loads(self._item_json)

    def as_dict(self):
        return {'item_json': self._item_json,
                'values': [[value is not MISSING, None if value is MISSING else value]
                           for value in self._values],
                'descending': list(self._descending)}

    @classmethod
    def from_dict(cls, value):
        if (type(value) is not dict or set(value) != {'item_json', 'values', 'descending'}
                or type(value['item_json']) is not str
                or type(value['values']) is not list or type(value['descending']) is not list):
            raise ResultContractError('Exact query spool row fields are required')
        for operand in value['values']:
            if (type(operand) is not list or len(operand) != 2
                    or type(operand[0]) is not bool or (not operand[0] and operand[1] is not None)):
                raise ResultContractError('An explicit Missing/scalar operand is required')
        return cls(json.loads(value['item_json']),
                   tuple(operand[1] if operand[0] else MISSING for operand in value['values']),
                   tuple(value['descending']))


def _row_key(row):
    if type(row) is not _QueryRow:
        raise ResultContractError('A typed query spool row is required')
    keys = tuple(_scalar_key(value, '/sort/' + str(index))
                 for index, value in enumerate(row._values))
    return tuple(_Descending(key) if descending else key
                 for key, descending in zip(keys, row._descending)) + (row.item['id'],)


class _QuerySpool(DiagnosticSpool):
    _record_field = 'query_row'
    _format = 'query-spool-v1'
    _ordering = 'query-scalar-directions-id-v1'
    _cursor_format = 'query-page-cursor-v1'
    _sort_key = staticmethod(_row_key)
    _decode = staticmethod(_QueryRow.from_dict)


def _rows(selection, artifacts, ordering):
    descending = tuple(item[1] for item in ordering)
    for item in selection.items:
        artifact = artifacts[item['id']]
        values = tuple(resolve_tokens(artifact, tokens, rule_id='query-sort', at=pointer + '/key')
                       for tokens, _, pointer in ordering)
        yield _QueryRow(item, values, descending)


class QueryWork:
    """Owned external sort followed by forward-only exact page construction.

    The caller chooses a new private spool root outside explicit protected
    boundaries. close releases handles and preserves all owned files. State is
    descriptive only; it grants no permission to reopen arbitrary spool paths.
    """

    def __init__(self, root, records, query, *, project, protected_roots,
                 configuration=None, batch_bytes=65536):
        _positive(batch_bytes)
        if type(query) is not NormalizedQuery:
            raise ModelError('normalized_query_required')
        records = tuple(_sequence(records))
        data = query.data
        ordering = []
        for index, item in enumerate(data['sort']):
            pointer = '/sort/' + str(index)
            key = item['key']
            tokens = parse_pointer(key, rule_id='query-sort', at=pointer + '/key') if key.startswith('/') else (key,)
            if tokens and tokens[0] == 'verification_result':
                raise ModelError('query_verification_provider_required', pointer=pointer)
            ordering.append((tokens, item['direction'] == 'desc', pointer))
        self._selection = select_query(records, query, project=project, configuration=configuration)
        ids = set(self._selection.artifact_ids)
        artifacts = {record.identity.id: record.data for record in records if record.identity.id in ids}
        self._offset, self._limit = data['offset'], data['limit']
        self._items = []
        self._visited = self._units = 0
        self._cursor = self._result = None
        self._failed = self._closed = False
        self._sort = DiagnosticSort(root, _rows(self._selection, artifacts, ordering),
                                    protected_roots=protected_roots, batch_bytes=batch_bytes,
                                    _spool_type=_QuerySpool)

    @property
    def state(self):
        return {'format': 'query-work-cursor-v1',
                'phase': 'complete' if self._result is not None else 'failed' if self._failed else
                         'cancelled' if self._closed else 'delivery' if self._cursor is not None else 'sorting',
                'query_sha256': self._selection.query_sha256,
                'inputs_sha256': self._selection.inputs_sha256,
                'units_completed': self._units, 'visited_records': self._visited,
                'retained_items': len(self._items), 'complete': self._result is not None,
                'durable_checkpoint': False, 'sort': self._sort.state,
                'delivery': None if self._cursor is None else self._cursor.state}

    @property
    def result(self):
        if self._result is None or self._closed:
            raise ValueError('Query work has no available complete page')
        return self._result

    def advance(self, units=1):
        _positive(units)
        if self._closed:
            raise ValueError('Query work is closed')
        try:
            for _ in range(units):
                if self._result is not None:
                    break
                if not self._sort.state['complete']:
                    self._sort.advance(1)
                elif self._cursor is None:
                    spool = self._sort.result
                    if spool.manifest['record_count'] != self._selection.total:
                        raise SafetyViolation('Query spool changed the complete selection count')
                    self._cursor = spool.cursor()
                elif self._visited < min(self._offset + self._limit, self._selection.total):
                    rows = self._cursor.read_page(1)
                    if len(rows) != 1:
                        raise SafetyViolation('Query spool delivery ended before the exact page')
                    if self._visited >= self._offset:
                        self._items.append(rows[0].item)
                    self._visited += 1
                else:
                    # Sorting is complete even for an empty page or limit zero.
                    # Check the owned run once more before publishing a result.
                    with self._sort.result.cursor():
                        pass
                    self._result = QueryPage(self._selection, self._items, self._offset, self._limit)
                    self._cursor.close()
                self._units += 1
            return self.state
        except BaseException:
            self._failed = True
            self._result = None
            self.close()
            raise

    def close(self):
        if not self._closed:
            self._closed = True
            self._sort.close()

    def __enter__(self):
        if self._closed:
            raise ValueError('Query work is closed')
        return self

    def __exit__(self, *unused):
        self.close()
