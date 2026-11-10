"""Small shared profiling values and exclusive artifact paths."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from verification_support.runtime_store import journal_path

MARKER = 'specroad-test-profiles'
VERSION = 1


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return sha256(encoded(value).encode()).hexdigest()


def test_key(nodeid):
    return sha256(nodeid.encode()).hexdigest()


def write_json(path, value):
    path = Path(path)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(encoded(value) + '\n')


def output_path(root, value):
    return journal_path(Path(value).expanduser().absolute(), root)


def relative_selector(root, selector):
    if not isinstance(selector, str) or not selector or '\0' in selector or selector.startswith('-'):
        raise ValueError('Use a test file, directory or pytest node ID')
    filename, separator, suffix = selector.partition('::')
    source = Path(filename)
    source = source if source.is_absolute() else Path(root) / source
    source = source.resolve()
    if not source.is_relative_to(Path(root).resolve() / 'tests') or not source.exists():
        raise ValueError('Test selections must belong to this repository/tests')
    return source.relative_to(Path(root).resolve()).as_posix() + (separator + suffix if separator else '')
