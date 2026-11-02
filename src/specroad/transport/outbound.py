"""One explicit outbound operation using the public source-safe PH contract.

Live project observations are coverage/currentness witnesses only. The project
payload is produced exclusively from native effective snapshot bytes. No PH
Result, Git patch, receipt or canonical model format is interpreted here.
"""
import os
from hashlib import sha256
from pathlib import Path
import stat
import tempfile

from ..bundles._project_snapshot import ProjectBundleSnapshot
from ..bundles.project import prepare_project_bundle
from ..bundles.verification import verify_bundle
from ..bundles.publication import _publish
from ..changes._lock_files import LockFiles
from ..changes._staging_files import _write_new
from ..changes.lock_values import ProjectLockError
from ..changes.staging_values import StagingError
from ..model.paths import project_path as safe_project_path
from ..model.canonical import canonical_json_bytes
from ._core_artifact import core_artifact
from ._contract import MAX_ARTIFACT_BYTES
from ._export_boundary import authorize, binding, repository_root, pre_bootstrap_output
from ._files import PassiveFile, absolute, directory, overlap, require
from ._handoff import OutboundContainer, reference_runtime_member
from .runtime import PatchHarborRuntime, _check_api
from .snapshots import TransportFailure, api_failure, read_snapshot


def _api_call(api, call, *args, **kwargs):
    try:
        return call(*args, **kwargs)
    except TransportFailure:
        raise
    except (api.PatchHarborError, OSError, TypeError, ValueError) as error:
        raise api_failure(api, error) from error


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


class OutboundExport:
    """Own a single source binding, observed inputs and explicit operating area.

    Preparation contains no producing PH call. Execution is never retried by
    this object. Partial outputs remain available as actual operating facts.
    """

    def __init__(self, root, *, patchharbor_pyz, patchharbor_pyz_sha256,
                 specroad_pyz, specroad_pyz_sha256, output_root, output, allow_existing=False):
        self.project = directory(root)
        self.output = directory(output_root, owned=True)
        pre_bootstrap_output(self.output.root)
        require(not overlap(self.project.root, self.output.root), 'transport_output_inside_project')
        safe_project_path(output)
        self.output_name = output
        require(allow_existing or not os.path.lexists(self.output.root / output), 'transport_output_exists', 6)
        self.core, self.core_identity = core_artifact(specroad_pyz, specroad_pyz_sha256)
        self.runtime_input = PassiveFile(patchharbor_pyz, expected_sha256=patchharbor_pyz_sha256,
                                         limit=MAX_ARTIFACT_BYTES)
        self.observation = ProjectBundleSnapshot(self.project.root)
        self.workspace = None
        self._workspace_boundary = None
        self.api = self.context = self.plan = None
        self.effects = {'export_started': False, 'reference_published': None}
        self._attempted = False

    def prepare(self, *, expected=None):
        require(self.api is None, 'transport_already_prepared', 6)
        self.verify_inputs()
        # Runtime preparation writes only into a newly owned private child of the
        # caller's explicit external area. They are disclosed even on failure.
        self.workspace = Path(tempfile.mkdtemp(prefix='.specroad-outbound-', dir=self.output.root))
        self._workspace_boundary = directory(self.workspace, owned=True)
        self.effects['private_workspace'] = str(self.workspace)
        self.runtime = PatchHarborRuntime(self.runtime_input.path,
            trusted_artifact_sha256=self.runtime_input.sha256, workspace=self.workspace / 'runtime',
            safe_reference=True)
        self.api = self.runtime.load_api(required=('context', 'prepare_reference_export', 'bundle'))
        self.context = _api_call(self.api, self.api.context, self.project.root, capture_mode='safe')
        repo = repository_root(self.context)
        self.project_path = self.project.root.relative_to(repo).as_posix()
        self.plan = _api_call(self.api, self.api.prepare_reference_export, repo,
            output_directory=self.output.root, expected_context=self.context)
        self.effects.update(_api_call(self.api, authorize, self.api, self.context, self.plan,
            project_root=self.project.root, output_root=self.output.root))
        self.verify_inputs()
        if expected is not None:
            require(self.expected_source() == expected, 'transport_work_source_changed', 6)
        return self.effects.copy()

    def verify_inputs(self):
        self.project._check_root(); self.output._check_root()
        directory(self.output.root, owned=True)
        if self._workspace_boundary is not None:
            self._workspace_boundary._check_root()
            info = self.workspace.lstat()
            require(info.st_uid == os.getuid() and not stat.S_IMODE(info.st_mode) & 0o077,
                    'transport_private_workspace_changed')
        self.core.verify_current(); self.runtime_input.verify_current()
        self.observation.verify_current()
        if self.api is not None:
            # Retained API objects do not bypass the adapter's continued private
            # copy, source, module-origin and capability checks.
            require(self.runtime.load_api(required=('context', 'prepare_reference_export', 'bundle')) is self.api,
                    'transport_runtime_api_changed')

    def expected_source(self):
        required = {**self.observation.payloads, **self.observation.receipts.payloads}
        return {'source_binding': binding(self.context), 'repository_root': str(repository_root(self.context)),
                'project_path': self.project_path, 'plan_sha256': self.plan.binding_sha256,
                'coverage_sha256': sha256(canonical_json_bytes([
                    {'path': name, 'sha256': sha256(raw).hexdigest()} for name, raw in sorted(required.items())
                ])).hexdigest(), 'core_sha256': self.core.sha256, 'patchharbor_pyz_sha256': self.runtime_input.sha256}

    def capture(self):
        require(self.api is not None and not self._attempted, 'transport_export_not_prepared', 6)
        self._attempted = True
        self.verify_inputs()
        _check_api(self.api, safe_reference=True)
        _api_call(self.api, authorize, self.api, self.context, self.plan,
                  project_root=self.project.root, output_root=self.output.root)
        self.effects['export_started'] = True
        bundle = _api_call(self.api, self.api.bundle, repository_root(self.context),
                           capture_mode='safe', export_plan=self.plan)
        self.effects['reference_published'] = str(bundle.path)
        result = PassiveFile(bundle.path)
        self.effects['reference_sha256'] = result.sha256
        return {'path': str(result.path), 'sha256': result.sha256,
                'source_binding': binding(bundle.context), 'effects': dict(self.effects)}

    def assemble(self, reference):
        self.verify_inputs()
        _api_call(self.api, authorize, self.api, self.context, self.plan,
                  project_root=self.project.root, output_root=self.output.root)
        require(binding(self.context) == reference['source_binding'], 'transport_reference_context_mismatch', 6)
        result = PassiveFile(reference['path'], expected_sha256=reference['sha256'])
        require(result.path.parent == self.output.root, 'transport_reference_outside_output')
        self.effects = dict(reference['effects'])
        self.effects['projection_workspace'] = str(self.workspace)
        snapshot = read_snapshot(self.api, result.path, expected_sha256=result.sha256)
        require(binding(self.context) == binding(snapshot.context),
                'transport_reference_context_mismatch', 6)
        result.runtime_member = reference_runtime_member(snapshot)
        self.verify_inputs()
        # A freshly generated private projection has no foreign files or links.
        # Every byte originates in the native reader's validated effective layer.
        prefix = '' if self.project_path == '.' else self.project_path + '/'
        selected = {name[len(prefix):]: file for name, file in snapshot.effective.files.items()
                    if name.startswith(prefix)}
        required = {**self.observation.payloads, **self.observation.receipts.payloads}
        for name, raw in required.items():
            require(name in selected and selected[name].content == raw,
                    'transport_required_snapshot_bytes_missing', 6)
        # Receipt completion is historical here: its original root/inode must
        # not be rebound to this temporary projection. The live witness already
        # checked native local admission; the bundle verifier below checks the
        # original portable receipt bytes, without executing retry/publication.
        projection_names = set(self.observation.payloads)
        marker = self.observation._previous_manifest
        if marker is not None:
            require('bundle-manifest.json' in selected and selected['bundle-manifest.json'].content == marker,
                    'transport_required_snapshot_bytes_missing', 6)
        projection = _write_projection(self._workspace_boundary, selected, projection_names)
        project = prepare_project_bundle(projection)
        if self.observation.receipts.payloads:
            from ..bundles.container import BundleContainer, encode_bundle
            metadata = {k: v for k, v in project.manifest.items() if k != 'entries'}
            receipt_bytes = {n: selected[n].content for n in self.observation.receipts.payloads}
            project = BundleContainer(encode_bundle(metadata, {**project.files, **receipt_bytes}))
        require(project.files == required, 'transport_project_inventory_mismatch', 6)
        verify_bundle(project.source_bytes, expected_sha256=project.sha256)
        container = OutboundContainer(project, result, snapshot,
            self.core, self.core_identity, self.project_path)

        def verify_current():
            self.verify_inputs(); result.verify_current()
            _api_call(self.api, authorize, self.api, self.context, self.plan,
                      project_root=self.project.root, output_root=self.output.root)
            current = _api_call(self.api, self.api.context, repository_root(self.context), capture_mode='safe')
            require(current == self.context, 'transport_source_changed', 6)

        verify_current()
        return container, verify_current

    def publish(self, container, verify_current, *, recover=False):
        verify_current()
        path = self.output.root / self.output_name
        if recover and os.path.lexists(path):
            from ..bundles.publication import publication_result
            existing = PassiveFile(path, expected_sha256=container.sha256)
            require(existing.raw == container.source_bytes, 'transport_published_bytes_changed', 6)
            verify_current(); existing.verify_current()
            published = publication_result(container, self.output_name)
        else:
            published = _publish(container, self.observation.source, verify_current,
                                 self.output_name, str(self.output.root))
        return {**published, 'transport': dict(self.effects), 'runtime_profile': 'python-present'}

    def execute(self):
        reference = self.capture()
        container, verify_current = self.assemble(reference)
        return self.publish(container, verify_current)
