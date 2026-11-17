"""Bounded run-profile storage; selection aliases share their existing JSON key."""
import json
from pathlib import Path

from .config import MAX_HOST_INPUT_BYTES, read_json
from .contract import validate_profile

ENCODING = 'selected-key-alias-v1'


def read_profile(path):
    value = read_json(path, strict=True)
    if isinstance(value, dict) and 'storage_encoding' in value:
        if value.pop('storage_encoding') != ENCODING or not isinstance(value.get('selected'), dict):
            raise ValueError('Invalid host profile storage encoding')
        # None refers only to this entry's key, never to another input/path.
        # Reusing the parsed string avoids recursive or unbounded expansion.
        value['selected'] = {node: node if identity is None else identity
                             for node, identity in value['selected'].items()}
    return validate_profile(value)


def write_profile(path, profile):
    validate_profile(profile)
    raw = json.dumps(profile, sort_keys=True).encode('utf-8')
    if len(raw) > MAX_HOST_INPUT_BYTES:
        stored = dict(profile, storage_encoding=ENCODING,
                      selected={node: None if node == identity else identity
                                for node, identity in profile['selected'].items()})
        raw = json.dumps(stored, sort_keys=True, separators=(',', ':')).encode('utf-8')
    if len(raw) > MAX_HOST_INPUT_BYTES:
        raise ValueError('Unsafe or oversized host input')
    path = Path(path)
    path.write_bytes(raw)
    path.chmod(0o600)
