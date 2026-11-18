"""Lazy own public records over immutable byte-derived registry indices."""
from collections.abc import Mapping
from copy import deepcopy
from types import MappingProxyType

from .language_values import RegistryRecord


class _RegistryRecords(Mapping):
    """Instance-owned public records over private immutable parser values."""
    def __init__(self, values):
        self._values = values
        self._materialized = {}

    def __getitem__(self, identity):
        if identity not in self._materialized:
            record = RegistryRecord(*self._values[0][identity])
            self._materialized.setdefault(identity, record)
        return self._materialized[identity]

    def __iter__(self):
        return iter(self._values[0])

    def __len__(self):
        return len(self._values[0])

    def range_keys(self):
        return self._values[1]

    def __deepcopy__(self, memo):
        # Only immutable private strings/tuples are shared. Even records that
        # a caller mutated with object.__setattr__ stay local to their copy.
        result = type(self)(self._values)
        memo[id(self)] = result
        result._materialized = deepcopy(self._materialized, memo)
        return result


def _record_values(records):
    return (MappingProxyType({identity: (record.kind, record.value, record.fields)
                              for identity, record in records.items()}),
            tuple(identity for identity in records if '..' in identity[1]))


def _fresh_records(values):
    return _RegistryRecords(values)
