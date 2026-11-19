"""Explicit, descriptor-bound analyzer files; no operational project writes."""
from hashlib import sha256
import os
from pathlib import Path
import secrets

from ..security import ProjectBoundary
from ..security import paths as guards
from ..model.paths import project_path
from ..model.configuration import ProjectConfiguration
from ..changes._lock_files import LockFiles
from ..changes._staging_files import _write_new
from ..changes._publication_io import replace_bound_image
from ._values import AnalyzerError, require, decode


def canonical_path(value, cwd):
    # Validate the spelling before Path can collapse dot/empty components.
    require(isinstance(value, str) and bool(value), 'analyzer_path_required', exit_code=2)
    project_path(value[1:] if value.startswith('/') else value)
    path = Path(value) if value.startswith('/') else Path(cwd) / value
    require(path.parent.resolve(strict=True) == path.parent, 'analyzer_linked_parent', exit_code=7)
    return path


class InputFile:
    def __init__(self, value, cwd):
        self.path = canonical_path(value, cwd)
        self.boundary = ProjectBoundary(self.path.parent)
        self.raw = self.boundary.read_bytes(self.path.name)

    def current(self):
        require(self.path.parent.resolve(strict=True) == self.path.parent,
            'analyzer_input_parent_changed', exit_code=6)
        require(self.boundary.read_bytes(self.path.name) == self.raw,
            'analyzer_input_changed', exit_code=6)


def output_target(value, *, root, output_root, cwd):
    """An explicit external root, or the selected project's generated directory."""
    if output_root is not None:
        require(Path(output_root).is_absolute(), 'analyzer_absolute_output_root_required', exit_code=2)
        project_path(output_root[1:])
        boundary = ProjectBoundary(output_root)
        require(str(boundary.root) == output_root, 'analyzer_output_root_not_canonical', exit_code=7)
        for parent in (boundary.root, *boundary.root.parents):
            require(not (parent / 'specroad.json').exists() and not (parent / 'specroad.json').is_symlink(),
                'analyzer_external_output_in_project', exit_code=7)
        if root is not None:
            require(not (Path(root).is_relative_to(boundary.root) or boundary.root.is_relative_to(root)),
                'analyzer_output_root_overlaps_project', exit_code=7)
        path = project_path(value)
        current = lambda: boundary._check_root()
    elif root is not None:
        boundary = ProjectBoundary(root)
        raw = boundary.read_bytes('specroad.json')
        configuration = ProjectConfiguration(decode(raw))
        path = configuration.generated_path + '/analysis/' + project_path(value)
        def current():
            require(boundary.read_bytes('specroad.json') == raw, 'analyzer_configuration_changed', exit_code=6)
    else:
        # Projectless output still requires a declared external root; it cannot
        # accidentally write into an enclosing, unselected project's model.
        raise AnalyzerError('analyzer_output_root_required', exit_code=2)
    require(not any(part.casefold() in ('.specroad', 'specroad.json') for part in path.split('/')),
        'analyzer_output_forbidden', exit_code=7)
    return boundary, path, current


def publish(raw, value, *, root, output_root=None, cwd, check_inputs):
    boundary, path, current = output_target(value, root=root, output_root=output_root, cwd=cwd)
    parts = path.split('/')
    digest = sha256(raw).hexdigest()
    with LockFiles(boundary.root) as files:
        require(files.boundary._root_identity == boundary._root_identity, 'analyzer_output_root_changed', exit_code=6)
        # Existing parents are intentional: no mkdir, lock files or hidden roots.
        with files.directory(parts[:-1]) as directory:
            require(directory is not None, 'analyzer_output_parent_required', exit_code=5)
            def check_directory():
                check_inputs(); current(); boundary._check_root()
                require(boundary.root.resolve(strict=True) == boundary.root, 'analyzer_output_root_changed', exit_code=6)
                with files.directory(parts[:-1]) as now:
                    require(now is not None and guards._identity(os.fstat(now)) == guards._identity(os.fstat(directory)),
                        'analyzer_output_directory_changed', exit_code=6)
            def check_target():
                check_directory()
                try:
                    info = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
                except FileNotFoundError:
                    return
                guards._regular(info)
                require(info.st_nlink == 1, 'analyzer_output_hardlink', exit_code=7)
                raise AnalyzerError('analyzer_output_conflict', exit_code=6)
            check_target()
            pending = '.analyzer-' + secrets.token_hex(16) + '.tmp'
            identity = _write_new(directory, pending, raw)
            try:
                replace_bound_image(directory, pending, directory, parts[-1], size=len(raw), digest=digest,
                    identity=identity, create_only=True,
                    source_changed=lambda: AnalyzerError('analyzer_output_image_changed', exit_code=6),
                    before_replace=check_target)
            except FileExistsError as error:
                raise AnalyzerError('analyzer_output_conflict', exit_code=6) from error
            check_directory()
    return dict(path=str(boundary.root/path), size=len(raw), sha256=digest, changed=True)
