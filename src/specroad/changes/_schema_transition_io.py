"""Descriptor-bound full inventory and external backup observations."""
from pathlib import Path
from types import SimpleNamespace
import os
from ..security import paths as guards
from ._journal_io import _read
from .schema_transition_values import require, SchemaTransitionError

def read(files, path, *, optional=False):
    with files.directory(tuple(path.split('/')[:-1])) as parent:
        if parent is None:
            if optional: return None
            raise SchemaTransitionError('transition_resource_missing')
        try:
            name=path.rsplit('/',1)[-1]
            info=os.stat(name,dir_fd=parent,follow_symlinks=False)
            require(info.st_dev==os.fstat(files.root_fd).st_dev
                    and os.fstat(parent).st_dev==info.st_dev and not info.st_mode&0o7000,
                    'transition_unsafe_image',exit_code=7)
            return _read(parent,name,expected_identity=guards._identity(info))
        except FileNotFoundError:
            if optional: return None
            raise


def external_backup(files, descriptor, *, plan=None):
    from ..documents._export_targets import _output_boundary
    from ..bundles.migration_source import verify_source_backup
    source = SimpleNamespace(boundary=files.boundary)
    output = _output_boundary(descriptor['output_root'], source)
    path = Path(descriptor['path']).relative_to(output.root).as_posix()
    raw = output.read_bytes(path)
    require(len(raw) == descriptor['size'], 'transition_backup_changed')
    if plan is None:
        backup = verify_source_backup(raw, expected_sha256=descriptor['sha256'],
            expected_source_files_sha256=descriptor['source_files_sha256'])
    else:
        from ._snapshot_dispatch import verify_backup
        backup = verify_backup(plan,raw,descriptor)
    require(output.read_bytes(path) == raw, 'transition_backup_changed')
    return backup


def project_files(files, *, exclude=()):
    from ..migration._backup_source import _scan
    def selected(names):
        return tuple(p for p in names if not any(p == root or p.startswith(root + '/') for root in exclude))
    before = selected(_scan(files))
    observed, modes, identities = {}, {}, {}
    for path in before:
        with files.directory(tuple(path.split('/')[:-1])) as parent:
            require(parent is not None, 'transition_source_changed')
            name = path.rsplit('/', 1)[-1]
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            guards._regular(info)
            from ..force_operations import permit
            require(permit(info.st_dev == os.fstat(files.root_fd).st_dev and info.st_nlink == 1
                    and not info.st_mode & 0o7000, gate='safety:source_metadata', subject=path,
                    observed={'device': info.st_dev, 'links': info.st_nlink, 'mode': info.st_mode},
                    requested={'device': os.fstat(files.root_fd).st_dev, 'links': 1, 'special_bits': False}),
                    'transition_unsafe_source', exit_code=7)
            identities[path] = guards._identity(info)
            observed[path] = _read(parent, name, expected_identity=identities[path])
            modes[path] = info.st_mode & 0o777
    require(selected(_scan(files)) == before, 'transition_source_changed')
    return observed, modes, identities
