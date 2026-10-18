"""Shared source and output-target admission for generated view publication."""
import os
from pathlib import Path

from ..model.paths import PathClass, project_path
from ..security import ProjectBoundary
from .exports import ViewExportError


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


def _check_source(model, source):
    source.check_current()
    if (source.boundary.root != Path(model.binding.source_root)
            or source.boundary._root_identity != model.binding.root_identity
            or source.configuration.project_id != model.binding.project_id
            or source.configuration_bytes != model.configuration_bytes):
        raise ViewExportError('view_export_source_mismatch', exit_code=6)


def _target_path(path, source, output_root):
    path = project_path(path)
    parts = tuple(path.split('/'))
    if ((output_root is None and (source.classify(path) != PathClass.GENERATED
                                 or path == source.configuration.generated_path))
            or any(part.casefold() in ('.specroad', 'specroad.json') for part in parts)):
        raise ViewExportError('view_export_target_forbidden', path=path, exit_code=7)
    return path, parts
