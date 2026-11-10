"""Explicit offline, byte-preserving migration; never launch or resume a worker."""
from contextlib import ExitStack
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile
import zipfile
from .errors import ControlError
from .local import Paths, outside, private_dir, lock, json_read, json_write, read_private


def fail(message):
    raise ControlError('migration_blocked', message)


def digest(path):
    with path.open('rb') as stream:
        value = sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def inventory(old):
    files = {}
    roots = [('config', old.config.parent), ('state', old.state), ('run', old.runtime)]
    for prefix, root in roots:
        outside(root)
        if not root.exists():
            continue
        private_dir(root)
        for path in sorted(root.rglob('*')):
            outside(path)
            info = path.lstat()
            if path == old.socket and stat.S_ISSOCK(info.st_mode):
                continue  # A socket is an endpoint, never a portable record.
            if stat.S_ISDIR(info.st_mode):
                private_dir(path)
                continue
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_nlink != 1 or info.st_mode & 0o077):
                fail('Legacy data contains a linked, public or non-regular file.')
            if prefix == 'state' and old.runtime in path.parents:
                continue  # Legacy fallback state/run is mapped exactly once.
            name = prefix + '/' + path.relative_to(root).as_posix()
            files[name] = {'source': str(path), 'sha256': digest(path), 'size': info.st_size}
    return files


def stopped(paths, *, allow_uninstalled=False):
    from . import service
    if allow_uninstalled and not paths.unit.exists():
        props = service.inspect(paths)
        service.verify_properties(paths, props)
        if props.get('LoadState') != 'not-found':
            fail('A loaded unit without its owned file requires review.')
    else:
        props = service.verify_owned(paths)
    if props.get('ActiveState') not in ('inactive', 'failed'):
        fail('Stop Control and let current work finish before migration.')
    reply = service.checked(['show', paths.unit.name, '--property=MainPID', '--value'])
    if reply.stdout.strip() != '0':
        fail('The service still has a process.')


def sqlite_check(path):
    if not path.exists():
        return
    # Inspect an isolated copy so SQLite cannot modify preserved WAL/SHM bytes.
    with tempfile.TemporaryDirectory(prefix='.sqlite-check-', dir=path.parent) as directory:
        target = Path(directory)/path.name
        for suffix in ('', '-wal', '-shm'):
            source = path.with_name(path.name + suffix)
            if source.exists():
                shutil.copyfile(source, target.with_name(target.name + suffix))
        connection = sqlite3.connect(target.as_uri() + '?mode=ro', uri=True)
        try:
            if connection.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                fail('The copied history did not pass SQLite integrity verification.')
        finally:
            connection.close()


def copy_record(source, target, expected):
    outside(target)
    private_dir(target.parent)
    if target.exists():
        info = target.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or digest(target) != expected):
            fail('Existing target data differs; it will not be overwritten.')
        return
    fd, temporary = tempfile.mkstemp(prefix='.migration-', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as output, source.open('rb') as stream:
            shutil.copyfileobj(stream, output, 1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        if digest(Path(temporary)) != expected or digest(source) != expected:
            fail('Source changed during copy.')
        os.link(temporary, target, follow_symlinks=False)  # Never replace existing data.
        fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        os.unlink(temporary)


def backup(root, files, unit):
    private_dir(root / 'backups')
    target = root / 'backups/migration-source.zip'
    metadata = {'files': files, 'unit_sha256': sha256(read_private(unit)).hexdigest()}
    if target.exists():
        with zipfile.ZipFile(target) as archive:
            if json.loads(archive.read('inventory.json')) != metadata or archive.testzip():
                fail('A conflicting migration backup already exists.')
            for name, row in files.items():
                if sha256(archive.read(name)).hexdigest() != row['sha256']:
                    fail('Backup verification failed.')
        return digest(target)
    fd, tmp = tempfile.mkstemp(prefix='.backup-', dir=target.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('inventory.json', json.dumps(metadata, sort_keys=True))
            archive.writestr('systemd/specroad-control.service', read_private(unit))
            for name, row in files.items():
                archive.write(row['source'], name)
        with zipfile.ZipFile(tmp) as archive:
            if archive.testzip():
                fail('Backup CRC verification failed.')
            for name, row in files.items():
                if sha256(archive.read(name)).hexdigest() != row['sha256']:
                    fail('Backup source changed.')
        with open(tmp, 'rb') as stream:
            os.fsync(stream.fileno())
        os.link(tmp, target)
    finally:
        os.unlink(tmp)
    return digest(target)


def migrate(paths, *, legacy_config=None):
    if paths.instance != 'default':
        fail('Legacy migration belongs to the default instance; named instances require explicit setup.')
    old = Paths.legacy()
    if legacy_config:
        old = Paths(outside(Path(legacy_config)), old.state, old.runtime, old.unit)
    if old.config.name != 'config.toml':
        fail('Legacy migration requires config.toml; no implicit configuration rename.')
    if paths.config != paths.home / 'config/config.toml':
        fail('Migration requires the canonical config destination.')
    for source in (old.config.parent, old.state, old.runtime):
        if source == paths.home or source in paths.home.parents or paths.home in source.parents:
            fail('Source and target overlap.')
    private_dir(paths.home)
    with ExitStack() as stack:
        stack.enter_context(lock(paths.home / 'migration.lock'))
        for directory in (old.state, paths.state):
            for name in ('operation.lock', 'worker.lock'):
                stack.enter_context(lock(directory / name))
        stopped(old)
        journal_path = paths.home / 'migration.json'
        journal = json_read(journal_path)
        if journal and journal.get('phase') == 'completed':
            # A finished migration is not a restore operation; new data may have advanced.
            if journal.get('legacy_config') != str(old.config):
                fail('This data home was migrated from another configuration.')
            return {'migrated': False, 'already_migrated': True, 'started': False}
        files = inventory(old)
        inventory_sha = sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
        if 'config/config.toml' not in files:
            fail('Legacy configuration is missing.')
        if not journal:
            existing = [p for d in (paths.home/'config', paths.state, paths.runtime) if d.exists()
                        for p in d.rglob('*') if p.is_file() and p.name not in ('operation.lock','worker.lock')]
            if existing:
                fail('Target contains data without a migration journal.')
            needed = sum(row['size'] for row in files.values()) * 2
            if shutil.disk_usage(paths.home).free < needed + 10_000_000_000:
                fail('Insufficient free disk space for backup and copy with 10 GB reserve.')
            backup_sha = backup(paths.home, files, old.unit)
            journal = {'format_version': 1, 'phase': 'copying', 'legacy_config': str(old.config),
                       'inventory_sha256': inventory_sha, 'backup_sha256': backup_sha}
            json_write(journal_path, journal)
        elif (type(journal.get('format_version')) is not int or journal['format_version'] != 1
              or journal.get('phase') != 'copying' or journal.get('legacy_config') != str(old.config)
              or journal.get('inventory_sha256') != inventory_sha):
            fail('Legacy files changed after the migration began.')
        if backup(paths.home, files, old.unit) != journal['backup_sha256']:
            fail('The migration backup changed.')
        for name, row in files.items():
            copy_record(Path(row['source']), paths.home / name, row['sha256'])
        if inventory(old) != files:
            fail('Legacy files changed before migration completed.')
        sqlite_check(paths.state / 'automation.sqlite3')
        # SQLite read-only validation may create sidecars, but never modifies rows.
        for name, row in files.items():
            if digest(paths.home / name) != row['sha256']:
                fail('Copied bytes changed during verification.')
        for directory in (paths.home/'config', paths.state, paths.runtime, paths.logs):
            private_dir(directory)
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        json_write(journal_path, dict(journal, phase='completed'))
    return {'migrated': True, 'data_home': str(paths.home), 'started': False,
            'history_rewritten': False, 'legacy_preserved': True}


def require_complete(paths):
    journal = json_read(paths.home / 'migration.json')
    if journal is not None and (type(journal.get('format_version')) is not int
                                or journal['format_version'] != 1 or journal.get('phase') != 'completed'):
        fail('An incomplete offline migration must be completed explicitly.')
