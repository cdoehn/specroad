"""Keep an extracted partial out of the existing complete-project reader.

This conservative boundary does not implement partial queries (15.f). The
retained bootstrap proof detects removal/replacement of the root manifest.
Neither record is an authenticated authority or a substitute for live gates.
"""
from hashlib import sha256

from ..model.errors import ModelError
from ..security import SafetyViolation
from ..storage.json_syntax import parse_json_object
from ._extraction_record import COMPLETED, FORMAT
from .errors import BundleError
from .manifest import MANIFEST_NAME, check_entries, owned_metadata


def _optional(boundary, path):
    try:
        return boundary.read_bytes(path)
    except FileNotFoundError:
        return None


def require_complete_root(boundary):
    proof = _optional(boundary, '/'.join((*COMPLETED, 'journal.json')))
    # Only roots published by this extractor have this additional proof.
    # Existing readers keep their own marker/error/freshness contracts; the
    # complete partial-command integration remains 15.f.
    if proof is None:
        return None, None
    raw = _optional(boundary, MANIFEST_NAME)
    try:
        if proof is not None:
            value = parse_json_object(proof)
            expected = value['entries'][MANIFEST_NAME]
            if (value['format'] != FORMAT or value['state'] != 'prepared' or raw is None
                    or expected['size'] != len(raw) or expected['sha256'] != sha256(raw).hexdigest()):
                raise SafetyViolation('Extracted bundle manifest changed or missing')
        if raw is not None:
            value = parse_json_object(raw)
            check_entries(value['entries'])
            metadata = owned_metadata({k: v for k, v in value.items() if k != 'entries'})
            if metadata['bundle_kind'] != 'project':
                raise SafetyViolation('A partial bundle is not a complete project')
    except (ModelError, BundleError, KeyError, TypeError) as error:
        raise SafetyViolation('Invalid extracted bundle metadata') from error
    return raw, proof
