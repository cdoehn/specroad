"""Lossless bounded storage for selections and host-specific runtime forecasts."""
import json
import math
from pathlib import Path

from .config import MAX_HOST_INPUT_BYTES, read_json
from .contract import validate_profile

ENCODING = 'selected-key-alias-v1'
FORECAST_ENCODING = 'selected-key-alias-and-forecasts-v1'
# The existing selection-key aliases already allow at most twice the input
# size after expansion. The additional codec keeps that same upper bound.
MAX_EXPANDED_PROFILE_BYTES = 2 * MAX_HOST_INPUT_BYTES


def expand_forecasts(value):
    estimates = value.get('estimates')
    if type(estimates) is not dict:
        raise ValueError('Invalid grouped runtime forecasts')
    base = dict(value, estimates={})
    validate_profile(base)
    identities = set(base['selected'].values())
    hosts = {row['host'] for row in base['workers'].values()}
    size = len(json.dumps(base, sort_keys=True).encode('utf-8'))
    if size > MAX_EXPANDED_PROFILE_BYTES:
        raise ValueError('Oversized expanded host profile')
    restored = {}
    for identity, values in estimates.items():
        if identity not in identities or type(values) is not dict or not values:
            raise ValueError('Unbound grouped runtime forecast')
        for host, duration in values.items():
            if (host not in hosts or type(duration) not in (int, float)
                    or not 0 <= duration <= 259200 or not math.isfinite(duration)):
                raise ValueError('Invalid grouped runtime forecast')
            key = identity + '\n' + host
            # Account before allocating the expanded mapping. JSON escaping,
            # UTF-8 and separators count; no compressed or recursive payload.
            size += (len(json.dumps(key).encode('utf-8')) + len(json.dumps(duration))
                     + (4 if restored else 2))
            if size > MAX_EXPANDED_PROFILE_BYTES:
                raise ValueError('Oversized expanded host profile')
            restored[key] = duration
    return dict(base, estimates=restored)


def group_forecasts(profile):
    identities = set(profile['selected'].values())
    hosts = {row['host'] for row in profile['workers'].values()}
    grouped = {}
    for key, duration in profile['estimates'].items():
        identity, separator, host = key.rpartition('\n')
        if not separator or identity not in identities or host not in hosts:
            # Historical free-form forecast keys retain their old encoding;
            # they are never silently discarded or reinterpreted.
            return None
        grouped.setdefault(identity, {})[host] = duration
    return grouped


def read_profile(path):
    value = read_json(path, strict=True)
    if isinstance(value, dict) and 'storage_encoding' in value:
        encoding = value.pop('storage_encoding')
        if encoding not in (ENCODING, FORECAST_ENCODING) or not isinstance(value.get('selected'), dict):
            raise ValueError('Invalid host profile storage encoding')
        # None refers only to this entry's key, never to another input/path.
        # Reusing the parsed string avoids recursive or unbounded expansion.
        value['selected'] = {node: node if identity is None else identity
                             for node, identity in value['selected'].items()}
        if encoding == FORECAST_ENCODING:
            value = expand_forecasts(value)
    return validate_profile(value)


def write_profile(path, profile):
    validate_profile(profile)
    raw = json.dumps(profile, sort_keys=True).encode('utf-8')
    expanded_size = len(raw)
    if len(raw) > MAX_HOST_INPUT_BYTES:
        stored = dict(profile, storage_encoding=ENCODING,
                      selected={node: None if node == identity else identity
                                for node, identity in profile['selected'].items()})
        raw = json.dumps(stored, sort_keys=True, separators=(',', ':')).encode('utf-8')
    if len(raw) > MAX_HOST_INPUT_BYTES and expanded_size <= MAX_EXPANDED_PROFILE_BYTES:
        grouped = group_forecasts(profile)
        if grouped is not None:
            stored.update(storage_encoding=FORECAST_ENCODING, estimates=grouped)
            raw = json.dumps(stored, sort_keys=True, separators=(',', ':')).encode('utf-8')
    if len(raw) > MAX_HOST_INPUT_BYTES:
        raise ValueError('Unsafe or oversized host input')
    path = Path(path)
    path.write_bytes(raw)
    path.chmod(0o600)
