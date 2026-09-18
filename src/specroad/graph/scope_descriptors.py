"""Immutable scope-v1 value; selector validation is shared independently.

No file loading, query execution, configuration filtering or scope closure.
"""
from dataclasses import dataclass
import json
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ._scope_selector_contract import _descriptor


@dataclass(frozen=True, init=False)
class ScopeDescriptor:
    """Validated selector shape. It does not claim full query/model validity."""
    _encoded: bytes

    def __init__(self, value):
        _descriptor(value)
        encoded = canonical_json_bytes(value)
        try:
            json.loads(encoded)
        except (ValueError, RecursionError) as error:
            raise ModelError('unsupported_scope_descriptor_nesting') from error
        object.__setattr__(self, '_encoded', encoded)

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
