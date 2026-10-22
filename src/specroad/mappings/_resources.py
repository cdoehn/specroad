"""Owned resource bytes and exact binding of explicitly supplied collections."""
from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_sha256
from ..storage.json_syntax import parse_json_object
from ._contract import MappingError, _MAPPING, _REGISTRY, _fail, _hash, _identity, _parse


@dataclass(frozen=True, init=False)
class ExchangeMapping:
    """Owned original bytes; a parsed resource alone is not a selection."""
    source_bytes: bytes
    mapping_id: str
    mapping_version: str
    sha256: str
    source_sha256: str

    def __init__(self, raw):
        value = _parse(raw, _MAPPING)
        self._initialize(raw, value)

    def _initialize(self, raw, value):
        for name, item in (("source_bytes", raw), ("mapping_id", value["mapping_id"]),
                           ("mapping_version", value["mapping_version"]),
                           ("sha256", canonical_json_sha256(value)),
                           ("source_sha256", sha256(raw).hexdigest())):
            object.__setattr__(self, name, item)

    @property
    def data(self):
        return parse_json_object(self.source_bytes)

    @property
    def key(self):
        return self.mapping_id + "@" + self.mapping_version

    def binding(self):
        return {"mapping_id": self.mapping_id, "mapping_version": self.mapping_version,
                "sha256": self.sha256}


@dataclass(frozen=True, init=False)
class ExternalIdentityRegistry(ExchangeMapping):
    """Passive registry bytes; binding to actual rules occurs at selection."""
    def __init__(self, raw):
        self._initialize(raw, _parse(raw, _REGISTRY))


def _index(resources, resource_type):
    if type(resources) not in (list, tuple):
        _fail("mapping_resource_sequence_required")
    indexed = {}
    for i, resource in enumerate(resources):
        if type(resource) is not resource_type:
            _fail("mapping_resource_type_required", "/resources/" + str(i))
        owned = resource_type(resource.source_bytes)
        if owned.key in indexed:
            _fail("mapping_duplicate_resource", "/resources/" + str(i))
        indexed[owned.key] = owned
    return indexed


def _select(indexed, key, expected_sha256):
    if type(key) is not str or key.count("@") != 1:
        _fail("mapping_exact_key_required")
    name, version = key.split("@")
    _identity({"mapping_id": name, "mapping_version": version})
    _hash(expected_sha256)
    if key not in indexed:
        _fail("mapping_resource_missing", "/resources")
    resource = indexed[key]
    if resource.sha256 != expected_sha256:
        raise MappingError("mapping_hash_mismatch", path=key, pointer="/sha256")
    return resource
