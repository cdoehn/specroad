"""Owned effective configuration values, detached from input records."""
from dataclasses import dataclass
from hashlib import sha256
import json

from ._resolution import resolve_values


@dataclass(frozen=True, init=False)
class EffectiveConfiguration:
    """Owned effective root values; no source mutation or configuration approval."""
    configuration_id: str
    source_sha256: str
    _encoded: bytes

    def __init__(self, records, configuration_id):
        selected, data = resolve_values(records, configuration_id)
        object.__setattr__(self, 'configuration_id', selected.id)
        object.__setattr__(self, 'source_sha256', sha256(selected.source_bytes).hexdigest())
        object.__setattr__(self, '_encoded', json.dumps(data, ensure_ascii=False,
                                                     allow_nan=False).encode('utf-8'))

    @property
    def data(self):
        return json.loads(self._encoded)

    @property
    def effective_values(self):
        return self.data['effective_values']

    @property
    def dimensions(self):
        return self.data['dimensions']

    @property
    def validation_scope(self):
        return 'supplied_root_configuration_only'
