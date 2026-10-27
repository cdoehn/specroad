"""External Restore input/output adapters, never recovery authorization.

Publication uses the existing generated-output boundaries and native durable
image writer. Reading reconstructs the original passive bindings, not a fresh
inventory: an interrupted execution must reach its specialized recovery checks.
"""
import os
from pathlib import Path
import secrets
from types import SimpleNamespace

from ..changes._lock_files import LockFiles
from ..changes._publication_io import replace_bound_image
from ..changes._staging_files import _write_new
from ..documents._export_targets import _check_external, _output_boundary, _target_path
from ..security import paths as guards
from ._execution_binding import original_active
from ._inventory import boundary, check_aliases, read_source
from ._journal_selection import journal_selection
from ._observations import verify_live
from .values import RestoreError, RestorePlan, guarded, require


@guarded
def publish_restore_plan(raw, *, output_root, output):
    """Create one complete external plan without changing any project bytes.

    The existing output root must be explicit and outside every project. An
    existing target is never overwritten, even for identical bytes. Errors
    preserve actual external images; publication confers no execution rights.
    """
    require(isinstance(output_root, (str, Path)), 'restore_output_root_required', exit_code=2)
    require(type(output) is str and output, 'restore_output_path_required', exit_code=2)
    plan = RestorePlan(raw)
    data = plan.data
    try:
        project = boundary(data['project_root'])
        origin = boundary(data['source']['root'])
    except FileNotFoundError as error:
        raise RestoreError('restore_input_disappeared', exit_code=6) from error
    # Generated-output admission only needs the project boundary. Do not load
    # the damaged current configuration as an allegedly valid ProjectSource.
    source = SimpleNamespace(boundary=project)
    try:
        output_boundary = _output_boundary(output_root, source)
    except FileNotFoundError as error:
        raise RestoreError('restore_output_root_missing', exit_code=5) from error
    path, parts = _target_path(output, source, output_root)

    def current():
        verify_live(plan, project, origin)
        _check_external(output_boundary, source)
        check_aliases(output_boundary, path)

    current()
    with LockFiles(output_boundary.root) as files:
        require(files.boundary._root_identity == output_boundary._root_identity,
                'restore_output_root_changed', exit_code=6)
        files.acquire()  # External directory mutex; no project owner record.

        def absent():
            check_aliases(output_boundary, path)
            with files.directory(parts[:-1]) as parent:
                if parent is not None:
                    try:
                        os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
                    except FileNotFoundError:
                        return
                    raise RestoreError('restore_output_exists', path=path, exit_code=6)

        current()
        absent()
        with files.directory(parts[:-1], create=True) as parent:
            parent_identity = guards._identity(os.fstat(parent))

            def target_current():
                current()
                absent()
                with files.directory(parts[:-1]) as actual:
                    require(actual is not None and guards._identity(os.fstat(actual)) == parent_identity,
                            'restore_output_directory_changed', exit_code=6)

            target_current()
            pending = '.specroad-restore-plan-' + secrets.token_hex(16) + '.tmp'
            identity = _write_new(parent, pending, plan.source_bytes)
            try:
                replace_bound_image(parent, pending, parent, parts[-1],
                    size=len(plan.source_bytes), digest=plan.sha256, identity=identity,
                    create_only=True, before_replace=target_current,
                    source_changed=lambda: RestoreError('restore_output_image_changed', exit_code=6))
            except FileExistsError as error:
                raise RestoreError('restore_output_exists', path=path, exit_code=6) from error
        current()
        require(read_source(output_boundary, path) == plan.source_bytes,
                'restore_published_plan_changed', exit_code=6)
        current()
    return plan


@guarded
def read_restore_inputs(plan_root, plan_path, *, selection_root=None, selection_path=None):
    """Return owned plan and optional original selection bytes, without writes.

    This is not live preflight, a new plan, or authority to execute. The native
    executor still checks the current source/inventory or exact interrupted
    effects, current authorization and lock. Retained original bytes remain
    readable when the source has disappeared after complete publication.
    """
    require(isinstance(plan_root, (str, Path)) and type(plan_path) is str and plan_path,
            'restore_plan_file_required', exit_code=2)
    require((selection_root is None) == (selection_path is None),
            'restore_selection_file_required', exit_code=2)
    if selection_root is not None:
        require(isinstance(selection_root, (str, Path))
                and type(selection_path) is str and selection_path,
                'restore_selection_file_required', exit_code=2)
    plan_boundary = boundary(plan_root)
    raw = read_source(plan_boundary, plan_path)
    plan = RestorePlan(raw)
    selection_boundary = None
    selection = None
    if selection_root is not None:
        selection_boundary = boundary(selection_root)
        selection = read_source(selection_boundary, selection_path)
    journal_selection(plan, selection, original_active(plan))
    try:
        require(read_source(plan_boundary, plan_path) == raw,
                'restore_plan_file_changed', exit_code=6)
        if selection_boundary is not None:
            require(read_source(selection_boundary, selection_path) == selection,
                    'restore_selection_file_changed', exit_code=6)
    except FileNotFoundError as error:
        raise RestoreError('restore_file_disappeared', exit_code=6) from error
    return plan, selection
