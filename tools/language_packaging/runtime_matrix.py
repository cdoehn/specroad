"""Explicit operator-selected test interpreters; never a project/runtime input.

The local manifest is a prerequisite, not successful integration evidence.
Only actual Apply tests can establish that its runtimes execute the adapter.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import re

from .inventory import NUMPY
from .wheels import regular_bytes


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate runtime manifest field')
        result[key] = value
    return result


def _absolute(value):
    if type(value) is not str or not Path(value).is_absolute() or '..' in Path(value).parts:
        raise ValueError('Explicit absolute runtime path required')
    path = Path(value)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Linked runtime input')
    return path


def load_runtime_matrix(path=None):
    path = path or os.environ.get('SPECROAD_LANGUAGE_TEST_RUNTIMES') or (
        Path.home() / '.config/specroad/language-test-runtimes.json')
    try:
        raw = regular_bytes(path)
    except FileNotFoundError as error:
        raise ValueError('Missing explicitly prepared CPython language runtime matrix') from error
    if len(raw) > 128 * 1024:
        raise ValueError('Oversized runtime manifest')
    value = json.loads(raw, object_pairs_hook=_unique)
    if (type(value) is not dict or set(value) != {'format_version', 'kind', 'wheelhouse', 'interpreters'}
            or type(value['format_version']) is not int or value['format_version'] != 1
            or value['kind'] != 'specroad-language-test-runtimes-v1'
            or type(value['interpreters']) is not dict or set(value['interpreters']) != set(NUMPY)):
        raise ValueError('Incomplete or unknown CPython 3.10–3.14 runtime manifest')
    wheelhouse = _absolute(value['wheelhouse'])
    if not wheelhouse.is_dir():
        raise ValueError('Missing offline wheelhouse')
    executables = set()
    for minor, row in value['interpreters'].items():
        if (type(row) is not dict or set(row) != {'executable', 'version', 'sha256'}
                or type(row['version']) is not str or re.fullmatch(re.escape(minor) + r'\.[0-9]+', row['version']) is None
                or type(row['sha256']) is not str or re.fullmatch(r'[0-9a-f]{64}', row['sha256']) is None):
            raise ValueError('Invalid runtime binding')
        executable = _absolute(row['executable'])
        if str(executable) in executables:
            raise ValueError('Duplicate runtime executable')
        executables.add(str(executable))
        if not os.access(executable, os.X_OK) or sha256(regular_bytes(executable)).hexdigest() != row['sha256']:
            raise ValueError('Runtime executable differs from explicit binding')
    return value
