"""Developer verification: common responsibilities."""

import hashlib
import json
from pathlib import Path
import re
import stat


class CatalogError(ValueError):
    """Invalid test binding or unavailable current evidence."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    # Developer report encoding, deliberately not the future model JCS contract.
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise CatalogError("Duplicate JSON key")
        value[key] = item
    return value


def _reject_constant(value):
    raise CatalogError("Non-finite JSON value")


def read_object(path):
    path = Path(path)
    if not stat.S_ISREG(path.lstat().st_mode):
        raise CatalogError("Manifest must be a regular file")
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                           parse_constant=_reject_constant)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise CatalogError("Invalid manifest JSON") from error
    if not isinstance(value, dict):
        raise CatalogError("Manifest must be an object")
    return value, sha256(raw)


def _strings(value, *, nonempty=False):
    return (type(value) is list and (bool(value) or not nonempty)
            and all(type(item) is str and bool(item) for item in value)
            and len(value) == len(set(value)))


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


