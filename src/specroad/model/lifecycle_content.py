"""Existing 9.6.3 content projection shared by Writer and Merge.

This is not the different verification-context projection from Annex L.
"""
from .canonical import canonical_json_sha256

_CONTENT_EXCLUDED = frozenset(('revision', 'created_at', 'created_by', 'updated_at', 'updated_by', 'maturity'))

def _content_hash(artifact):
    # Internal owned candidate: maturity can still require a dedicated gate.
    return canonical_json_sha256({key: value for key, value in artifact.items() if key not in _CONTENT_EXCLUDED})
