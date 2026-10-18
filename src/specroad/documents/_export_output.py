"""Create one generated view file using the existing native atomic writer.

Initial scope: an existing directory under the configured generated path, on
native Linux storage. No directory creation, overwrite, external target, lock,
journal or receipt. Interrupted private preparation files remain inspectable;
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
from ..security import paths as guards
from ..storage.project import ProjectSource
from .exports import ViewExportError, export_view


def write_view_export(model, view_id, *, source, path, output_format='json', configuration_id=None):
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
    if (source.classify(path) != PathClass.GENERATED
            or path == source.configuration.generated_path
            or any(part.casefold() in ('.specroad', 'specroad.json') for part in parts)):
        raise ViewExportError('view_export_target_forbidden', path=path, exit_code=7)
    # Complete admission and serialization precede even private output creation.
    raw = export_view(model, view_id, output_format=output_format, configuration_id=configuration_id)
    digest = sha256(raw).hexdigest()
    with LockFiles(source.boundary.root) as files:
        # Only the existing descriptor traversal is used. acquire() and all
        # operational/lock-file methods are deliberately outside this path.
        with files.directory(parts[:-1]) as directory:
            if directory is None:
                raise ViewExportError('view_export_directory_required', path=path, exit_code=5)

            def check_target():
                check_source()
                with files.directory(parts[:-1]) as current:
                    if (current is None or guards._identity(os.fstat(current))
                            != guards._identity(os.fstat(directory))):
                        raise ViewExportError('view_export_directory_changed', path=path, exit_code=6)
                try:
                    os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
                except FileNotFoundError:
                    return
                raise ViewExportError('view_export_target_exists', path=path, exit_code=6)

            check_target()
            pending = '.view-export-' + secrets.token_hex(16) + '.tmp'
            identity = _write_new(directory, pending, raw)
            replace_bound_image(directory, pending, directory, parts[-1],
                size=len(raw), digest=digest, identity=identity, create_only=True,
                source_changed=lambda: ViewExportError('view_export_image_changed', path=path, exit_code=6),
                before_replace=check_target)
            check_source()
    return {'format_version': 1, 'kind': 'view-export-publication-v1',
        'path': path, 'size': len(raw), 'sha256': digest, 'generated': True,
        'normative': False, 'source_validation_scope': 'supplied_snapshot',
        'full_validation_passed': False, 'approval_granted': False}
