"""Descriptor-bound observations and shared image moves for schema transitions."""
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import os
from ..security import paths as guards
from ..model.canonical import canonical_json_bytes as jcs
from ..storage.json_syntax import parse_json_object as parsed
from ._journal_io import _read
from ._staging_files import _write_new, _image
from ._publication_io import replace_bound_image
from .publication_check import _rights
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


def write_new(files, path, raw):
    with files.directory(tuple(path.split('/')[:-1]), create=True) as parent:
        _rights(parent, path)
        require(os.fstat(parent).st_dev == os.fstat(files.root_fd).st_dev,
                'transition_cross_device', exit_code=7)
        return _write_new(parent, path.rsplit('/', 1)[-1], raw)


def complete_owned_image(files, path, expected, *, guard):
    """Resume only an exact prefix of a deterministic, transaction-owned image.

    No truncation or speculative cleanup: every existing byte is proven before
    appending. The independently durable backup and plan supply the full bytes.
    """
    guard()
    old = read(files, path, optional=True)
    if old is None:
        write_new(files, path, expected)
        return
    require(expected.startswith(old), 'transition_partial_image_changed')
    if old == expected: return
    with files.directory(tuple(path.split('/')[:-1])) as parent:
        name = path.rsplit('/',1)[-1]
        identity = _image(parent, name, len(old), sha256(old).hexdigest())
        fd = os.open(name, os.O_WRONLY | os.O_NOFOLLOW | getattr(os,'O_CLOEXEC',0), dir_fd=parent)
        try:
            require(guards._identity(os.fstat(fd)) == identity, 'transition_partial_image_changed')
            guard()
            require(_read(parent,name,expected_identity=identity) == old, 'transition_partial_image_changed')
            os.lseek(fd,len(old),os.SEEK_SET)
            remaining = memoryview(expected)[len(old):]
            while remaining:
                written = os.write(fd,remaining)
                if written <= 0: raise OSError('Incomplete owned image write')
                remaining = remaining[written:]
            os.fsync(fd)
        finally: os.close(fd)
        os.fsync(parent)
        _image(parent,name,len(expected),sha256(expected).hexdigest(),identity=identity)


def external_backup(files, descriptor):
    from ..documents._export_targets import _output_boundary
    from ..bundles.migration_source import verify_source_backup
    source = SimpleNamespace(boundary=files.boundary)
    output = _output_boundary(descriptor['output_root'], source)
    path = Path(descriptor['path']).relative_to(output.root).as_posix()
    raw = output.read_bytes(path)
    require(len(raw) == descriptor['size'], 'transition_backup_changed')
    backup = verify_source_backup(raw, expected_sha256=descriptor['sha256'],
        expected_source_files_sha256=descriptor['source_files_sha256'])
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
            require(info.st_dev == os.fstat(files.root_fd).st_dev and info.st_nlink == 1
                    and not info.st_mode & 0o7000, 'transition_unsafe_source', exit_code=7)
            identities[path] = guards._identity(info)
            observed[path] = _read(parent, name, expected_identity=identities[path])
            modes[path] = info.st_mode & 0o777
    require(selected(_scan(files)) == before, 'transition_source_changed')
    return observed, modes, identities


def check_parents(files, paths):
    result = {}
    for path in paths:
        parts = tuple(path.split('/')[:-1])
        for index in range(len(parts) + 1):
            key = parts[:index]
            if key in result: continue
            with files.directory(key) as fd:
                result[key] = None if fd is None else guards._identity(os.fstat(fd))
                if fd is not None:
                    require(os.fstat(fd).st_dev == os.fstat(files.root_fd).st_dev,
                            'transition_cross_device', exit_code=7)
    return result


def move_image(files, work, path, raw, *, before, mode, guard, after):
    """Keep durable original images; only an owned temporary copy is moved."""
    guard()
    if raw is None:
        require(before is not None, 'transition_delete_without_source')
        with files.directory(tuple(path.split('/')[:-1])) as parent:
            require(parent is not None, 'transition_parent_changed')
            name = path.rsplit('/', 1)[-1]
            _rights(parent, path)
            _image(parent, name, len(before), sha256(before).hexdigest())
            guard()
            os.unlink(name, dir_fd=parent)
            after()
            os.fsync(parent)
        return
    token = sha256((path + ':' + sha256(raw).hexdigest()).encode()).hexdigest() + '.bin'
    staged = work + '/moves/' + token
    complete_owned_image(files, staged, raw, guard=guard)
    with files.directory(tuple(path.split('/')[:-1]), create=True) as parent:
        require(parent is not None, 'transition_parent_changed')
        _rights(parent, path)
        with files.directory(tuple(staged.split('/')[:-1])) as temp:
            require(os.fstat(parent).st_dev == os.fstat(temp).st_dev, 'transition_cross_device', exit_code=7)
            identity = _image(temp, token, len(raw), sha256(raw).hexdigest())
            guard()
            replace_bound_image(temp, token, parent, path.rsplit('/', 1)[-1],
                size=len(raw), digest=sha256(raw).hexdigest(), identity=identity,
                mode=mode, create_only=before is None, single_link_create=True,
                source_changed=lambda: SchemaTransitionError('transition_pending_image_changed'),
                before_replace=guard, after_replace=lambda info: after())
