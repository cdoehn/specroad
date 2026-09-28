"""Owned value-only request bindings; no routing or permission side effects."""
from dataclasses import dataclass
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..storage.json_syntax import parse_json_object

AUTHORING_VERSION = "authoring-policy-v1"

@dataclass(frozen=True, init=False)
class AuthoringRequest:
    """Bound policy routing result, never a bearer capability for a writer."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use prepare_authoring_request or bind_plan_authoring')

    @classmethod
    def _create(cls, data):
        obj = object.__new__(cls)
        object.__setattr__(obj, '_encoded', canonical_json_bytes(data))
        return obj

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return canonical_json_sha256(self.data)

    def __bool__(self):
        raise TypeError('Inspect the route; this object is not a write permission')


