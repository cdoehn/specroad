"""Owned query row codec and M6 spool ordering; no query work lifecycle."""
from dataclasses import dataclass
from functools import total_ordering
import json

from ..diagnostics.spooling import DiagnosticSpool
from ..result_contract import ResultContractError
from ..srx import MISSING
from ..srx.pointers import resolve_tokens
from .paging import _scalar_key


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
