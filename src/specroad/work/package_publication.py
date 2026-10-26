"""Explicit external files for the existing read-only Work package contract.

This host API retains the checkpoint lease through create-only publication.
It neither registers a Work CLI nor exports active native transactions. A
verified local output is not proof of a copy outside the caller's sandbox.
"""
from hashlib import sha256
import os
import secrets

from ..changes._lock_files import LockFiles
from ..changes._publication_io import replace_bound_image
from ..changes._staging_files import _write_new
from ..model.paths import project_path
from ..security import ProjectBoundary, SafetyViolation
from ..security import paths as guards
from ..storage.archive import ArchiveError
from ._package_export_result import package_export_result
from .control import _initial
from .packages import _export_held, _supported
from .result_files import _ensure_work
from .resume import _runtime_build
from .root import _path


def _outside(boundary, store, held):
    boundary._check_root()
    root = boundary.root
    if root.resolve(strict=True) != root:
        raise SafetyViolation('Work export output root changed')
    store._location._outside(root)
    if root.is_relative_to(held.path) or held.path.is_relative_to(root):
        raise SafetyViolation('Work export must be outside its source root')
    for parent in (root, *root.parents):
        try:
            (parent / 'specroad.json').lstat()
        except FileNotFoundError:
            continue
        raise SafetyViolation('Work export output must be outside projects')


def _target(output_root, output, store, held):
    root = _path(output_root)
    if root.resolve(strict=True) != root:
        raise SafetyViolation('A canonical external output root is required')
    path = project_path(output)
    parts = tuple(path.split('/'))
    if any(p.casefold() in ('.specroad', 'specroad.json') for p in (*root.parts, *parts)):
        raise SafetyViolation('Work export cannot target project control paths')
    boundary = ProjectBoundary(root)
    _outside(boundary, store, held)
    return boundary, path, parts


def _vacant(files, parts):
    for index, name in enumerate(parts):
        with files.directory(parts[:index]) as parent:
            if parent is None:
                return
            if any(n != name and n.casefold() == name.casefold() for n in os.listdir(parent)):
                raise SafetyViolation('Work export names collide')
            if index == len(parts) - 1:
                try:
                    os.stat(name, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    return
                raise ArchiveError('work_export_output_exists', exit_code=6)


def publish_work_package(store, *, output_root, output):
    """Write one verified Work ZIP under an explicit separate existing root.

    Work/project/input boundaries remain untouched. The destination must be
    absent; failures preserve any actual private or final image. No handler,
    checkpoint publication, Recovery or automatic retry is performed.
    """
    build = _runtime_build(); _initial(store, build); _supported(store._initial)
    with store._location.inspect_checkpoint() as held:
        raw, pointer, current = _export_held(store, held, build)
        digest = sha256(raw).hexdigest()
        boundary, path, parts = _target(output_root, output, store, held)

        def check_source():
            _ensure_work(store, held, pointer, current, build)
            _outside(boundary, store, held)

        with LockFiles(boundary.root) as files:
            if files.boundary._root_identity != boundary._root_identity:
                raise ArchiveError('work_export_output_root_changed', exit_code=6)
            files.acquire()
            _vacant(files, parts)
            check_source()
            with files.directory(parts[:-1], create=True) as parent:
                directory_identity = guards._identity(os.fstat(parent))

                def check_target():
                    check_source()
                    _vacant(files, parts)
                    with files.directory(parts[:-1]) as actual:
                        if actual is None or guards._identity(os.fstat(actual)) != directory_identity:
                            raise ArchiveError('work_export_output_directory_changed', exit_code=6)

                check_target()
                temporary = '.specroad-work-export-' + secrets.token_hex(16) + '.tmp'
                identity = _write_new(parent, temporary, raw)
                try:
                    replace_bound_image(parent, temporary, parent, parts[-1],
                        size=len(raw), digest=digest, identity=identity, create_only=True,
                        before_replace=check_target,
                        source_changed=lambda: ArchiveError('work_export_image_changed', exit_code=6))
                except FileExistsError as error:
                    raise ArchiveError('work_export_output_exists', exit_code=6) from error
            check_source()
            if boundary.read_bytes(path) != raw:
                raise ArchiveError('work_export_published_bytes_changed', exit_code=6)
            check_source()
        value = current.as_dict()
        return package_export_result(work_id=value['work_id'],
            checkpoint_generation=value['checkpoint_generation'],
            checkpoint_sha256=value['checkpoint_sha256'], root=boundary.root,
            path=path, size=len(raw), digest=digest)
