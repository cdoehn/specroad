"""Resolve one durable runtime destination for writers, selection and CI export."""
import json
import os
from pathlib import Path
import stat

from .runtime_store import journal_path

POLICY = 'verification/test_runtime_policy.json'
SHARED = '../exchange/specroad-test-runtime-history.sqlite3'
LOCAL = 'build/test-runtime-history.sqlite3'
EXCHANGE = 'patchharbor-exchange'


def configured_exchange_database(root):
    """Use this repository's native Exchange, never another lane's default."""
    root = Path(root).resolve()
    directory = root / '.patchharbor'
    path = directory / 'config.json'
    if not os.path.lexists(path) and not os.path.lexists(directory / 'id'):
        # Standalone CI/test copies have no registered Apply destination.
        # Their private build store never falls back to a sibling lane.
        if directory.is_symlink():
            raise ValueError('Unsafe runtime Exchange configuration directory')
        return journal_path(root / LOCAL, root)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('Runtime history requires the local PatchHarbor configuration')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 65536:
            raise ValueError('Unsafe runtime Exchange configuration')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(65537)
        current = path.lstat()
        if len(raw) > 65536 or (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) != (
                current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns):
            raise ValueError('Runtime Exchange configuration changed while reading')
        value = json.loads(raw)
    finally:
        os.close(fd)
    if (type(value) is not dict or type(value.get('format_version')) is not int
            or value['format_version'] != 1 or type(value.get('exchange_directory')) is not str
            or not value['exchange_directory'] or '\x00' in value['exchange_directory']):
        raise ValueError('Invalid runtime Exchange configuration')
    exchange = Path(value['exchange_directory'])
    if not exchange.is_absolute():
        raise ValueError('Runtime Exchange must be an absolute directory')
    exchange = Path(os.path.abspath(exchange))
    if exchange == root or root in exchange.parents or exchange in root.parents:
        raise ValueError('Runtime Exchange must not overlap the source repository')
    result = journal_path(exchange / 'specroad-test-runtime-history.sqlite3', root)
    if not exchange.is_dir():
        raise ValueError('Configure the repository Exchange before recording runtimes')
    return result


def policy(root):
    path = Path(root) / POLICY
    if not os.path.lexists(path):
        return None
    if path.is_symlink() or not path.is_file():
        raise ValueError('Unsafe runtime policy')
    value = json.loads(path.read_bytes())
    if (set(value) != {'format_version', 'selection', 'database'}
            or type(value['format_version']) is not int or value['format_version'] != 1
            or value['selection'] != 'latest_valid_fifth'
            or value['database'] not in (LOCAL, SHARED, EXCHANGE)):
        raise ValueError('Unknown runtime history policy')
    if value['database'] == EXCHANGE:
        # Resolved path participates in the existing before/after policy checks.
        value = dict(value, database=str(configured_exchange_database(root)))
    return value


def database_path(root, config):
    return journal_path(Path(root) / (config['database'] if config else LOCAL), root)
