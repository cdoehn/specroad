"""Full-value JCS/SHA-256; application-specific projections remain explicit."""

from hashlib import sha256

from ._jcs_encoder import _chunks


def canonical_json_sha256(value):
    """Full-value JCS/SHA-256; callers must explicitly form other hash domains.

This is not a signature, review, verification result, or write authorization.
No audit field or application-defined self-hash is implicitly excluded.
    """
    digest = sha256()
    for chunk in _chunks(value):
        digest.update(chunk)
    return digest.hexdigest()


