"""Owned historical values; no acquisition, writer or authorization."""
from dataclasses import dataclass
from ..storage.json_syntax import parse_json_object as parsed


@dataclass(frozen=True)
class PublicationValidation:
    _raw: bytes
    @property
    def data(self): return parsed(self._raw)
