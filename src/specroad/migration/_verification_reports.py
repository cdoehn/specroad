"""Owned native verification reports; callers cannot grant authority with data."""
from dataclasses import dataclass
from hashlib import sha256
from ..model.canonical import canonical_json_bytes as jcs
from ..storage.json_syntax import parse_json_object as parsed

@dataclass(frozen=True, init=False)
class MigrationVerification:
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use the native migration verifier')

    @property
    def data(self):
        return parsed(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Migration verification is not write or release authority')


def _result(value):
    result = object.__new__(MigrationVerification)
    object.__setattr__(result, '_encoded', jcs(value))
    return result
