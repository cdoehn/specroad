"""Closed native JSON values and typed data refusal, without work execution."""

import re

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object


class WorkManifestError(ValueError):
    """Unusable work data, never a request to execute another command."""

    exit_code = 4


def _require(condition):
    if not condition:
        raise WorkManifestError('Invalid or incomplete work manifest')


def _object(value, fields):
    _require(type(value) is dict and all(type(key) is str for key in value)
             and set(value) == set(fields))


def _text(value):
    _require(type(value) is str and bool(value) and '\0' not in value)
    try:
        value.encode('utf-8')
    except UnicodeError as error:
        raise WorkManifestError('Invalid work text') from error


def _hash(value):
    _require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None)


def _count(value):
    _require(type(value) is int and 0 <= value <= 2**53 - 1)


def _path(value):
    _text(value)
    _require(not any(c in value for c in ('\\', ':'))
             and all(part not in ('', '.', '..') for part in value.split('/')))


def _plain_json(value):
    # Equality-based type membership can invoke a foreign metaclass. Admit
    # exact JSON types by identity before passing data to the shared encoder.
    stack, seen = [iter((value,))], set()
    while stack:
        try:
            item = next(stack[-1])
        except StopIteration:
            stack.pop()
            continue
        kind = type(item)
        if item is None or kind is str or kind is bool or kind is int or kind is float:
            continue
        _require(kind is dict or kind is list)
        if id(item) in seen:
            continue  # The canonical encoder separately rejects real cycles.
        seen.add(id(item))
        if kind is dict:
            _require(all(type(key) is str for key in item))
            stack.append(iter(item.values()))
        else:
            stack.append(iter(item))


def _copy(value):
    _plain_json(value)
    try:
        return parse_json_object(canonical_json_bytes(value))
    except ModelError as error:
        raise WorkManifestError('Invalid JSON work value') from error


def _parse(raw):
    _require(type(raw) is bytes)
    try:
        return parse_json_object(raw)
    except ModelError as error:
        raise WorkManifestError('Invalid JSON work bytes') from error
