"""Full source inventory/freshness on existing descriptor-bound I/O primitives."""
import os
import stat
from types import SimpleNamespace
from ..bundles.manifest import require
from ..bundles.migration_source import ADMIN_ROOTS, _safe
from ..changes._lock_files import LockFiles
from ..security import paths as guards
from ..storage.archive import validate_portable_archive_paths
from ..storage.operational_preflight import observe_operational_preflight

def _scan(handles):
    found, pending = [], [()]
    while pending:
        parts = pending.pop()
        with handles.directory(parts) as fd:
            require(fd is not None, 'migration_backup_source_changed')
            names = sorted(os.listdir(fd))
            _safe(len({n.casefold() for n in names}) == len(names), 'migration_backup_path_collision')
            for name in names:
                if not parts and name in ADMIN_ROOTS:
                    continue  # Outside the project; never open credentials/Git state.
                guards._parts(name)
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                directory = stat.S_ISDIR(info.st_mode)
                guards._regular(info, directory=directory)
                path = (*parts, name)
                if directory:
                    pending.append(path)
                else:
                    found.append('/'.join(path))
            require(sorted(os.listdir(fd)) == names, 'migration_backup_source_changed')
    validate_portable_archive_paths(found)
    return tuple(sorted(found, key=lambda p: p.encode('utf-8')))


def _observe(root):
    with LockFiles(root) as handles:
        boundary = handles.boundary
        def preflight():
            require(observe_operational_preflight(boundary)['consistency_state'] == 'consistent',
                    'migration_backup_operational_state')
        preflight(); names = _scan(handles)
        files = {p: boundary.read_bytes(p) for p in names}
        def check_current():
            boundary._check_root()
            with LockFiles(boundary.root) as current:
                require(current.boundary._root_identity == boundary._root_identity,
                        'migration_backup_source_changed')
                preflight()
                require(_scan(current) == names, 'migration_backup_source_changed')
                for p, raw in files.items():
                    require(boundary.read_bytes(p) == raw, 'migration_backup_source_changed')
                preflight()
                require(_scan(current) == names, 'migration_backup_source_changed')
        check_current()
    return files, SimpleNamespace(boundary=boundary), check_current
