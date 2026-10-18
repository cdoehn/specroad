"""Create one generated view file using the existing native atomic writer.

An existing generated directory or explicitly bound external directory on native
Linux storage. No directory creation, overwrite, lock, journal or receipt.
Interrupted private preparation files remain inspectable;
failure after publication may leave the complete target and never claims success.
"""
from hashlib import sha256
import os
from pathlib import Path
import secrets

from ..changes._lock_files import LockFiles
from ..changes._publication_io import replace_bound_image
from ..changes._staging_files import _write_new
from ..changes.target_model import TargetModel
from ..model.paths import PathClass, project_path
from ..security import ProjectBoundary
from ..security import paths as guards
from ..storage.project import ProjectSource
from .exports import ViewExportError, export_view


def _check_external(boundary, source):
    boundary._check_root()
    root = boundary.root
    if root.resolve(strict=True) != root:
        raise ViewExportError('view_export_external_root_changed', exit_code=6)
    if (root.is_relative_to(source.boundary.root) or source.boundary.root.is_relative_to(root)
            or boundary._root_identity == source.boundary._root_identity):
        raise ViewExportError('view_export_external_root_overlaps_project', exit_code=7)
    for parent in (root, *root.parents):
        try:
            (parent / 'specroad.json').lstat()
        except FileNotFoundError:
            continue
        raise ViewExportError('view_export_external_root_in_project', exit_code=7)


def _output_boundary(value, source):
    if value is None:
        return source.boundary
    if not isinstance(value, (str, Path)):
        raise ViewExportError('view_export_external_root_required', exit_code=2)
    raw = os.fspath(value)
    if not raw.startswith('/') or raw.startswith('//'):
        raise ViewExportError('view_export_external_root_required', exit_code=2)
    parts = project_path(raw[1:]).split('/')
    if any(part.casefold() in ('.specroad', 'specroad.json') for part in parts):
        raise ViewExportError('view_export_target_forbidden', exit_code=7)
    root = Path(raw)
    if root.resolve(strict=True) != root:
        raise ViewExportError('view_export_external_root_not_canonical', exit_code=7)
    boundary = ProjectBoundary(root)
    _check_external(boundary, source)
    return boundary


def write_view_export(model, view_id, *, source, path, output_format='json',
                      configuration_id=None, output_root=None):
    """Publish complete snapshot-derived bytes to one explicitly chosen new file."""
    if type(model) is not TargetModel or type(source) is not ProjectSource:
        raise ViewExportError('view_export_model_and_source_required')
    model = model.snapshot()

    def check_source():
        source.check_current()
        if (source.boundary.root != Path(model.binding.source_root)
                or source.boundary._root_identity != model.binding.root_identity
                or source.configuration.project_id != model.binding.project_id
                or source.configuration_bytes != model.configuration_bytes):
            raise ViewExportError('view_export_source_mismatch', exit_code=6)

    check_source()
    path = project_path(path)
    parts = tuple(path.split('/'))
    if ((output_root is None and (source.classify(path) != PathClass.GENERATED
                                 or path == source.configuration.generated_path))
            or any(part.casefold() in ('.specroad', 'specroad.json') for part in parts)):
        raise ViewExportError('view_export_target_forbidden', path=path, exit_code=7)
    boundary = _output_boundary(output_root, source)

    def check_location():
        check_source()
        boundary._check_root()
        if output_root is not None:
            _check_external(boundary, source)

    # Complete admission and serialization precede even private output creation.
    raw = export_view(model, view_id, output_format=output_format, configuration_id=configuration_id)
    digest = sha256(raw).hexdigest()
    with LockFiles(boundary.root) as files:
        if files.boundary._root_identity != boundary._root_identity:
            raise ViewExportError('view_export_directory_changed', path=path, exit_code=6)
        # Only the existing descriptor traversal is used. acquire() and all
        # operational/lock-file methods are deliberately outside this path.
        with files.directory(parts[:-1]) as directory:
            if directory is None:
                raise ViewExportError('view_export_directory_required', path=path, exit_code=5)

            def check_directory():
                check_location()
                with files.directory(parts[:-1]) as current:
                    if (current is None or guards._identity(os.fstat(current))
                            != guards._identity(os.fstat(directory))):
                        raise ViewExportError('view_export_directory_changed', path=path, exit_code=6)

            def check_target():
                check_directory()
                try:
                    os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
                except FileNotFoundError:
                    return
                raise ViewExportError('view_export_target_exists', path=path, exit_code=6)

            check_target()
            pending = '.view-export-' + secrets.token_hex(16) + '.tmp'
            identity = _write_new(directory, pending, raw)
            try:
                replace_bound_image(directory, pending, directory, parts[-1],
                    size=len(raw), digest=digest, identity=identity, create_only=True,
                    source_changed=lambda: ViewExportError('view_export_image_changed', path=path, exit_code=6),
                    before_replace=check_target)
            except FileExistsError as error:
                raise ViewExportError('view_export_target_exists', path=path, exit_code=6) from error
            check_directory()
    return {'format_version': 1, 'kind': 'view-export-publication-v1',
        'path': path if output_root is None else str(boundary.root / path),
        'size': len(raw), 'sha256': digest, 'generated': True,
        'normative': False, 'source_validation_scope': 'supplied_snapshot',
        'full_validation_passed': False, 'approval_granted': False}
