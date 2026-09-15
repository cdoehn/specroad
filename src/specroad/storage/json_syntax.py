"""UTF-8 JSON syntax and value decoding, without any resource-schema imports."""

import json

from ..model.errors import ModelError
from ..model.numbers import number_from_token


class _ObjectPairs(list):
    pass


class _Number(str):
    pass


def _pointer(parent, key):
    return parent + "/" + str(key).replace("~", "~0").replace("/", "~1")


def _materialize(value, pointer=""):
    if isinstance(value, _Number):
        return number_from_token(value, pointer=pointer)
    if isinstance(value, _ObjectPairs):
        result = {}
        for key, item in value:
            child = _pointer(pointer, key)
            if key in result:
                raise ModelError("duplicate_key", pointer=child)
            _materialize(key, child)
            result[key] = _materialize(item, child)
        return result
    if isinstance(value, list):
        return [_materialize(item, _pointer(pointer, index)) for index, item in enumerate(value)]
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeError as error:
            raise ModelError("invalid_unicode", pointer=pointer) from error
    return value


def parse_json_object(raw, *, path=None):
    """Parse exactly one object; keep original bytes and positions unchanged."""
    if not isinstance(raw, bytes):
        raise ModelError("bytes_required", path=path)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ModelError("invalid_utf8", path=path, position=error.start) from error
    try:
        value = json.loads(text, object_pairs_hook=_ObjectPairs, parse_constant=_Number,
                           parse_int=_Number, parse_float=_Number)
        if not isinstance(value, _ObjectPairs):
            raise ModelError("object_required", path=path)
        return _materialize(value)
    except json.JSONDecodeError as error:
        raise ModelError("invalid_json", path=path, position=error.pos,
                         line=error.lineno, column=error.colno) from error
    except ModelError as error:
        error.path = path
        raise
    except (ValueError, RecursionError) as error:
        raise ModelError("unsupported_json_value", path=path) from error


