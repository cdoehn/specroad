"""Owned effective configuration values, detached from input records."""
from dataclasses import dataclass
from hashlib import sha256
import json

from ._resolution import resolve_values
from ..model.canonical import canonical_json_bytes


@dataclass(frozen=True, init=False)
class EffectiveConfiguration:
    """Owned effective values and canonical chain binding; no source mutation."""
    configuration_id: str
    source_sha256: str
    _encoded: bytes
    _manifest: bytes

    def __init__(self, records, configuration_id):
        selected, data, manifest = resolve_values(records, configuration_id)
        object.__setattr__(self, 'configuration_id', selected.id)
        object.__setattr__(self, 'source_sha256', sha256(selected.source_bytes).hexdigest())
        object.__setattr__(self, '_encoded', json.dumps(data, ensure_ascii=False,
                                                     allow_nan=False).encode('utf-8'))
        object.__setattr__(self, '_manifest', canonical_json_bytes(manifest))

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
        return ('supplied_root_configuration_only' if len(self.manifest['configurations']) == 1
                else 'supplied_configuration_chain_only')

    @property
    def manifest(self):
        return json.loads(self._manifest)

    @property
    def sha256(self):
        return sha256(self._manifest).hexdigest()

    @property
    def binding(self):
        return {'configuration_id': self.configuration_id,
                'configuration_revision': self.data['configuration_revision'], 'sha256': self.sha256}
