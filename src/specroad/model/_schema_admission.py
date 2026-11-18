"""Conservative bounded cache keys; no vocabulary or instance acceptance."""
import json
import math


_SCHEMA_CACHE_BYTES = 512 * 1024
_SCHEMA_CACHE_NODES = 16384


def _schema_key(schema):
    """Bounded exact JSON-only admission; preserve order and scalar types.

    Other accepted Python values use the original interpreter unchanged.
    No user conversion hook is called to produce a cache key.
    """
    remaining = [_SCHEMA_CACHE_NODES, _SCHEMA_CACHE_BYTES]
    active = set()
    def plain(value):
        remaining[0] -= 1
        if remaining[0] < 0:
            return False
        if type(value) is str:
            remaining[1] -= len(value)
            return remaining[1] >= 0
        if value is None or type(value) is bool:
            return True
        if type(value) is int:
            return value.bit_length() <= 4096
        if type(value) is float:
            return math.isfinite(value)
        if type(value) not in (dict, list) or id(value) in active:
            return False
        active.add(id(value))
        try:
            if type(value) is dict:
                return all(type(k) is str and plain(k) and plain(v) for k, v in value.items())
            return all(plain(v) for v in value)
        finally:
            active.remove(id(value))
    try:
        if not plain(schema):
            return None
        encoded = json.dumps(schema, ensure_ascii=True, allow_nan=False, separators=(',', ':'))
        return encoded if len(encoded) <= _SCHEMA_CACHE_BYTES else None
    except RecursionError:
        return None
