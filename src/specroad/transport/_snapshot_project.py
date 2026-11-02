"""Native effective-byte projection and complete portable project packaging."""
import os

from ..bundles.project import prepare_project_bundle
from ..bundles.verification import verify_bundle
from ..changes._lock_files import LockFiles
from ..changes._staging_files import _write_new
from ..changes.lock_values import ProjectLockError
from ..changes.staging_values import StagingError
from ..model.paths import project_path as safe_project_path
from ._files import require
from .snapshots import TransportFailure


def _write_projection(boundary, selected, names):
    """Only native effective bytes enter an exclusively created private root."""
    projection = boundary.root / 'project'
    try:
        with LockFiles(boundary.root) as workspace:
            require(workspace.boundary._root_identity == boundary._root_identity,
                    'transport_private_workspace_changed', 6)
            workspace.acquire()
            require(not os.path.lexists(projection), 'transport_projection_exists', 6)
            os.mkdir('project', mode=0o700, dir_fd=workspace.root_fd)
            info = os.stat('project', dir_fd=workspace.root_fd, follow_symlinks=False)
            with LockFiles(projection) as files:
                require(files.boundary._root_identity == (info.st_dev, info.st_ino),
                        'transport_projection_changed', 6)
                files.acquire()
                for name in sorted(names):
                    safe_project_path(name)
                    parts = tuple(name.split('/'))
                    with files.directory(parts[:-1], create=True) as parent:
                        _write_new(parent, parts[-1], selected[name].content)
                files.check_root()
            workspace.check_root()
    except (ProjectLockError, StagingError) as error:
        raise TransportFailure(error.exit_code, reason=error.reason,
                               cause_type=type(error).__name__) from error
    return projection


def prepare_snapshot_project(snapshot, observation, project_path, workspace_boundary):
    prefix = '' if project_path == '.' else project_path + '/'
    selected = {name[len(prefix):]: file for name, file in snapshot.effective.files.items()
                if name.startswith(prefix)}
    required = {**observation.payloads, **observation.receipts.payloads}
    for name, raw in required.items():
        require(name in selected and selected[name].content == raw,
                'transport_required_snapshot_bytes_missing', 6)
    # Receipt completion is historical here: its original root/inode must
    # not be rebound to this temporary projection. The live witness already
    # checked native local admission; the bundle verifier below checks the
    # original portable receipt bytes, without executing retry/publication.
    projection_names = set(observation.payloads)
    marker = observation._previous_manifest
    if marker is not None:
        require('bundle-manifest.json' in selected and selected['bundle-manifest.json'].content == marker,
                'transport_required_snapshot_bytes_missing', 6)
    projection = _write_projection(workspace_boundary, selected, projection_names)
    project = prepare_project_bundle(projection)
    if observation.receipts.payloads:
        from ..bundles.container import BundleContainer, encode_bundle
        metadata = {k: v for k, v in project.manifest.items() if k != 'entries'}
        receipt_bytes = {n: selected[n].content for n in observation.receipts.payloads}
        project = BundleContainer(encode_bundle(metadata, {**project.files, **receipt_bytes}))
    require(project.files == required, 'transport_project_inventory_mismatch', 6)
    verify_bundle(project.source_bytes, expected_sha256=project.sha256)
    return project
