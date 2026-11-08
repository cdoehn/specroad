"""Local host configuration. No credentials or host inventory in the repository."""
from dataclasses import dataclass, asdict
import json
import math
import os
from pathlib import Path
import re

NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z')


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate host configuration field')
        result[key] = value
    return result


def read_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16_000_000:
        raise ValueError('Unsafe or oversized host input')
    return json.loads(path.read_bytes(), object_pairs_hook=unique)


def private_directory(path):
    path = Path(path).expanduser().absolute()
    for part in reversed((path, *path.parents)):
        if part.is_symlink():
            raise ValueError('Linked host state directory')
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    if path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
        raise ValueError('Host state directory must be owned by this user and mode 0700')
    return path


def state_directory():
    return private_directory(Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'specroad/test-hosts')


@dataclass(frozen=True)
class Host:
    name: str
    ssh: str | None
    directory: str
    workers: int = 10
    speed: float = 1.0
    persist: int = 1800

    def value(self):
        return asdict(self)


def host(value):
    if not isinstance(value, dict) or set(value) - {'name', 'ssh', 'directory', 'workers', 'speed', 'persist'}:
        raise ValueError('Unknown host fields; credentials belong in SSH, not this configuration')
    item = Host(**value)
    if not NAME.fullmatch(item.name) or item.ssh is not None and not NAME.fullmatch(item.ssh):
        raise ValueError('Host names and SSH aliases must be plain names')
    path = Path(item.directory)
    # No shell, execnet or rsync syntax is allowed in a remote work path.
    if not path.is_absolute() or '..' in path.parts or not re.fullmatch(r'/[A-Za-z0-9_./-]+', item.directory) or str(path) == '/':
        raise ValueError('Use a dedicated absolute host directory without spaces or metacharacters')
    if type(item.workers) is not int or not 1 <= item.workers <= 256:
        raise ValueError('Host workers must be in 1..256')
    if type(item.persist) is not int or not 0 <= item.persist <= 604800:
        raise ValueError('SSH idle persistence must be in 0..604800 seconds')
    if type(item.speed) not in (int, float) or not math.isfinite(item.speed) or not 0.01 <= item.speed <= 100:
        raise ValueError('Relative single-worker speed must be in 0.01..100')
    return item


def config_path(explicit=None):
    return Path(explicit or os.environ.get('SPECROAD_TEST_HOSTS') or Path.home() / '.config/specroad/test-hosts.json').expanduser()


def load(path):
    value = read_json(path)
    if not isinstance(value, dict) or set(value) != {'format_version', 'hosts'} or type(value['format_version']) is not int or value['format_version'] != 1:
        raise ValueError('Unknown host configuration version')
    items = [host(row) for row in value['hosts']]
    if not items or len(items) > 16 or len({h.name for h in items}) != len(items):
        raise ValueError('Configure 1..16 uniquely named hosts')
    if len({h.ssh for h in items}) != len(items):
        raise ValueError('An SSH alias (or the local host) may occur only once')
    return items
