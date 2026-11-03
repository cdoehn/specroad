"""Independent operating limit and fail-closed storage checks; no process killing."""
from copy import deepcopy
import os
from pathlib import Path
import threading
import time

from .errors import ControlError
from .execution_scope import execution_directory
from .local import REPO

from .disk_limits import GB, limits_path, minimum_bytes, read_limits, set_limit
CHECK_SECONDS = 5.0
STOP_ERRORS = frozenset({'low_disk_space', 'disk_space_unavailable'})


def locations(config, paths):
    result = [execution_directory(config), config.repository,
              config.repository.parent / 'specroad-apply', REPO, config.exchange,
              paths.state, Path('/var/tmp')]
    if config.codex_home is not None:
        result.append(config.codex_home)
    return list(dict.fromkeys(result))


def existing(path):
    """An uncreated child uses its nearest existing parent volume."""
    candidate = path
    while True:
        try:
            device = candidate.stat().st_dev
            return candidate, device
        except FileNotFoundError:
            if candidate.parent == candidate:
                raise
            candidate = candidate.parent


def sample(config, paths):
    volumes = {}
    for requested in locations(config, paths):
        path, device = existing(requested)
        info = os.statvfs(path)
        if path.stat().st_dev != device:
            raise OSError('Filesystem changed during capacity measurement.')
        size = info.f_frsize or info.f_bsize
        if type(info.f_bavail) is not int or type(size) is not int or info.f_bavail < 0 or size <= 0:
            raise ValueError('Invalid filesystem counters.')
        available = info.f_bavail * size
        volume = volumes.setdefault(device, {'device': device, 'paths': [], 'free_bytes': available})
        volume['paths'].append(str(requested))
        volume['free_bytes'] = min(volume['free_bytes'], available)
    return list(volumes.values())


class DiskGuard:
    def __init__(self, config, paths):
        self.config, self.paths = config, paths
        self.limits = read_limits(paths)
        self.mutex = threading.Lock()
        self.report = None
        self.failure = None

    def rebind(self, config):
        with self.mutex:
            self.config = config  # Preserve the limit and any already latched stop.

    def snapshot(self):
        with self.mutex:
            return deepcopy(self.report or {**self.limits, 'checked_at': None, 'filesystems': [], 'sufficient': None})

    def require(self):
        with self.mutex:
            if self.failure:
                raise ControlError(self.failure, 'The storage stop remains latched for this worker run.',
                                   details={'disk_space': deepcopy(self.report)})
            report = {**self.limits, 'checked_at': time.time(), 'filesystems': [], 'sufficient': False}
            try:
                report['filesystems'] = sample(self.config, self.paths)
                if not report['filesystems']:
                    raise ValueError('No filesystem evidence.')
                report['sufficient'] = all(item['free_bytes'] >= self.limits['min_free_bytes']
                                           for item in report['filesystems'])
                self.failure = None if report['sufficient'] else 'low_disk_space'
            except (OSError, ValueError, OverflowError, ControlError) as exc:
                self.failure = 'disk_space_unavailable'
                report['measurement_error'] = exc.code if isinstance(exc, ControlError) else type(exc).__name__
            self.report = {**report, 'error': self.failure}
            if self.failure:
                raise ControlError(self.failure, 'Storage protection requires a controlled stop.',
                                   details={'disk_space': deepcopy(self.report)})
            return deepcopy(self.report)


def status(paths):
    from .config import load
    guard = DiskGuard(load(paths, allow_deferred=True), paths)
    try:
        return guard.require()
    except ControlError as exc:
        if exc.code not in STOP_ERRORS:
            raise
        return guard.snapshot()
