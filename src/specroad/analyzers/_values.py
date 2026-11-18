"""Passive analyzer value checks; no project, plugin or runtime discovery."""
import re

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.metadata_fields import NAMESPACE_PATTERN
from ..storage.json_syntax import parse_json_object

IDENTIFIER = re.compile(r'[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*')


class AnalyzerError(ModelError):
    def __init__(self, reason, *, pointer='', exit_code=3):
        super().__init__(reason, pointer=pointer)
        self.exit_code = exit_code


def require(condition, reason, at='', *, exit_code=3):
    if not condition:
        raise AnalyzerError(reason, pointer=at, exit_code=exit_code)


def decode(raw):
    try:
        return parse_json_object(raw)
    except ModelError as error:
        raise AnalyzerError(error.reason, pointer=error.pointer) from error


def encoded(value):
    try:
        return canonical_json_bytes(value)
    except ModelError as error:
        raise AnalyzerError(error.reason, pointer=error.pointer) from error


def digest(value):
    return canonical_json_sha256(value)


def shape(value, fields, at='', optional=()):
    require(type(value) is dict, 'analyzer_object_required', at)
    require(set(fields) <= value.keys(), 'analyzer_missing_field', at)
    require(value.keys() <= set(fields) | set(optional), 'analyzer_unknown_field', at)


def identifier(value, at):
    require(type(value) is str and len(value) <= 128 and IDENTIFIER.fullmatch(value) is not None,
            'analyzer_invalid_identity', at)


def tokens(value, at, *, allowed=None):
    require(type(value) is list and bool(value), 'analyzer_nonempty_array_required', at)
    for entry in value:
        identifier(entry, at)
        if allowed is not None:
            require(entry in allowed, 'analyzer_unknown_value', at)
    require(value == sorted(set(value)), 'analyzer_sorted_unique_required', at)


def hash_value(value, at):
    require(type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value) is not None,
            'analyzer_invalid_sha256', at)


def extensions(value, at='/extensions'):
    require(type(value) is dict, 'analyzer_object_required', at)
    for key in value:
        require(type(key) is str and re.fullmatch(NAMESPACE_PATTERN, key) is not None,
                'analyzer_invalid_namespace', at)
