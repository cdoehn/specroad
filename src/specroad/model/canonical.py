"""Stable canonical-value API, separate from human-readable serialization.

Raw-object helpers use the strict reader before the pure JCS implementation.
Neither full-value hashing nor canonicalization invents a domain projection,
normalizes Unicode, changes a revision or authorizes a write.
"""

from ._jcs_encoder import canonical_json_bytes
from .hashes import canonical_json_sha256

__all__ = ("canonical_json_bytes", "canonical_json_sha256",
           "canonical_object_bytes", "canonical_object_sha256")


def canonical_object_bytes(raw, *, path=None):
    """Validate one original JSON object before canonicalization; no disk I/O."""
    from ..storage.json_syntax import parse_json_object
    return canonical_json_bytes(parse_json_object(raw, path=path))


def canonical_object_sha256(raw, *, path=None):
    """Hash an object's canonical values, not its original file bytes."""
    from ..storage.json_syntax import parse_json_object
    return canonical_json_sha256(parse_json_object(raw, path=path))
