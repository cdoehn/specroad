"""Read-only observations of existing native POSIX Apply locks and registration."""
import errno
import json
import os
from pathlib import Path
import stat
from uuid import UUID


def capture_native_file(path, limit):
    """Bounded stable read of an existing file; no links, devices or creation."""
    def signature(info):
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
                info.st_ctime_ns, info.st_mode, info.st_nlink)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
            raise ValueError('Keine begrenzte reguläre native Statusdatei')
        raw = stream.read(limit + 1)
        if len(raw) > limit or not signature(before) == signature(os.fstat(stream.fileno())) == signature(path.lstat()):
            raise ValueError('Native Statusdatei wurde während der Abfrage geändert')
    return raw


def native_registry(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Doppeltes Registry-Feld')
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=unique)
    if (type(value) is not dict or set(value) != {'format_version', 'repositories'}
            or type(value['format_version']) is not int or value['format_version'] != 1
            or type(value['repositories']) is not dict):
        raise ValueError('Unbekanntes Registry-Format')
    seen = set()
    for key, path in value['repositories'].items():
        if str(UUID(key)) != key or UUID(key).version != 4 or type(path) is not str or not Path(path).is_absolute():
            raise ValueError('Ungültige Registry-Zuordnung')
        canonical = Path(path).resolve()
        if canonical in seen:
            raise ValueError('Mehrdeutige Registry-Zuordnung')
        seen.add(canonical)
    return value['repositories']


def repository_availability(repository, processes):
    """Observe the existing PatchHarbor POSIX lock; never infer idle from /proc."""
    result = {'state': 'unknown', 'reason': 'lock_unavailable', 'reserved': False}
    if processes:
        return {**result, 'state': 'busy', 'reason': 'observed_process'}
    identity = repository / '.patchharbor/id'
    if not os.path.lexists(identity):
        return {**result, 'state': 'unregistered', 'reason': 'missing_local_identity'}
    if os.name != 'posix':
        return {**result, 'reason': 'lock_probe_unsupported'}
    try:
        identity_bytes = capture_native_file(identity, 128)
        repo_id = identity_bytes.decode('ascii').strip()
        if str(UUID(repo_id, version=4)) != repo_id or UUID(repo_id).version != 4:
            raise ValueError('Ungültige lokale Repository-ID')
        config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
        registry_path = config / 'patchharbor/registry.json'
        registry_bytes = capture_native_file(registry_path, 1_000_000)
        registered = native_registry(registry_bytes).get(repo_id)
        if registered is None:
            return {**result, 'state': 'unregistered', 'reason': 'missing_registry_entry'}
        if not isinstance(registered, str) or not Path(registered).is_absolute() or Path(registered).resolve() != repository:
            raise ValueError('Repository-Pfad stimmt nicht mit der Registry überein')
        state = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state')))
        lock = state / 'patchharbor/locks' / f'repository-{repo_id}.lock'
        result['lock_path'] = str(lock)
        import fcntl
        descriptor = os.open(lock, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('Keine eindeutige reguläre Sperrdatei')
            observation = 'free'
            try:
                fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except OSError as error:
                if error.errno in (errno.EAGAIN, errno.EACCES):
                    observation = 'busy'
                else:
                    raise
            current = lock.lstat()
            if (not stat.S_ISREG(current.st_mode) or current.st_nlink != 1
                    or (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino)):
                raise ValueError('Sperrdatei wurde während der Abfrage ersetzt')
            if (capture_native_file(identity, 128) != identity_bytes
                    or capture_native_file(registry_path, 1_000_000) != registry_bytes):
                raise ValueError('Registrierung wurde während der Abfrage geändert')
            return {**result, 'state': observation,
                    'reason': 'repository_lock_held' if observation == 'busy' else 'repository_lock_free'}
        finally:
            # Closing releases our shared probe even on a read/check failure.
            os.close(descriptor)
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        return {**result, 'detail': str(error)}
