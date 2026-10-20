"""Shared passive candidate structure; format adapters retain their contracts.

The adapters validate source-specific inputs and choose their existing encoder.
These helpers only assemble already interpreted measurements and detach output
bytes. They grant no execution, verification, import or publication authority.
"""
from hashlib import sha256

from ..model.canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object


class CandidateValue:
    """Read-only byte interface shared by the frozen, format-specific values."""

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()


def candidate_value(kind, value, *, encoder=canonical_json_bytes):
    result = object.__new__(kind)
    object.__setattr__(result, '_encoded', encoder(value))
    return result


def measurement(*, target, result, origin, **fields):
    """Retain one occurrence and its format-specific metadata without inference."""
    return {**fields, 'target': target, 'result': result, 'origin': origin}


def passive_status(**fields):
    """Common authority boundaries plus the adapter's existing status fields."""
    return {'test_code_executed': False, 'evidence_created': False,
            'project_targets_verified': False, 'full_verification_evaluated': False,
            'write_authorized': False, 'approval_granted': False, **fields}
