"""The fixed 10.3 top-level projection used by creation, checking and reviews."""
from hashlib import sha256

from ..model.canonical import canonical_json_bytes
from .errors import require


CONTENT_EXCLUSIONS = frozenset(('revision', 'created_at', 'created_by',
    'updated_at', 'updated_by', 'content_revision', 'content_sha256', 'maturity',
    'proposal_status', 'reviews', 'control_history'))


def content_projection(value):
    """Owned RFC-8785 bytes; nested homonyms and all other fields remain."""
    require(type(value) is dict, 'proposal_object_required')
    return canonical_json_bytes({k: v for k, v in value.items() if k not in CONTENT_EXCLUSIONS})


def content_sha256(value):
    return sha256(content_projection(value)).hexdigest()
