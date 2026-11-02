"""Explicit native inbound verification and safe creation of one new sandbox."""
from hashlib import sha256
from io import BytesIO
import os
import stat
from zipfile import ZipFile

from . import _contract
from ._files import PassiveFile, absolute, directory, overlap, require
from ._export_boundary import binding
from ._handoff import MAX_BYTES, reference_runtime_member
from ._opening_container import OpeningContainer
from ._opening_projection import verify_projection
from .runtime import PatchHarborRuntime, TransportUnavailable, _check_platform


def _external(path):
    parent = directory(path.parent, owned=True)
    require(not any(p.casefold() in ('.specroad', '.git', '.patchharbor') for p in path.parts),
            'opening_protected_path')
    for ancestor in (path.parent, *path.parent.parents):
        require(not os.path.lexists(ancestor / 'specroad.json'), 'opening_existing_project')
    return parent


class SandboxOpening:
    def __init__(self, filename, *, patchharbor_pyz, patchharbor_pyz_sha256,
                 runtime_workspace, expected_sha256=None, output=None):
        self.effects = {'runtime_workspace': None, 'sandbox_root': None, 'bootstrap_state': 'not_started'}
        self.source = PassiveFile(filename, expected_sha256=expected_sha256, limit=MAX_BYTES)
        self.container = OpeningContainer(self.source.raw)
        try:
            _check_platform()
        except TransportUnavailable as error:
            raise TransportUnavailable(error.reason, exit_code=5) from error
        self.pyz = PassiveFile(patchharbor_pyz, expected_sha256=patchharbor_pyz_sha256,
                               limit=_contract.MAX_ARTIFACT_BYTES)
        require(self.pyz.sha256 == _contract.ARTIFACT_SHA256
                and len(self.pyz.raw) == _contract.ARTIFACT_SIZE, 'unsupported_runtime_distribution')
        self.workspace = absolute(runtime_workspace)
        self.parent = _external(self.workspace)
        self.output = None if output is None else absolute(output)
        self.output_parent = None if self.output is None else _external(self.output)
        self.output_boundary = (directory(self.output, owned=True)
            if self.output is not None and os.path.lexists(self.output) else None)
        for path in (self.source.path, self.pyz.path):
            require(not overlap(self.workspace, path)
                    and (self.output is None or not overlap(self.output, path)), 'opening_input_overlap')
        require(self.output is None or not overlap(self.workspace, self.output), 'opening_workspace_overlap')
        require(not os.path.lexists(self.workspace), 'opening_workspace_exists', 6)
        self.expected_sha256 = expected_sha256
        self.workspace_boundary = self.reference = self.runtime = self.snapshot = None

    def verify_current(self):
        self.parent._check_root()
        _external(self.workspace)
        directory(self.source.path.parent)
        directory(self.pyz.path.parent)
        self.source.verify_current()
        self.pyz.verify_current()
        if self.output_parent is not None:
            self.output_parent._check_root()
            _external(self.output)
            if self.output_boundary is not None:
                self.output_boundary._check_root()
        if self.workspace_boundary is not None:
            self.workspace_boundary._check_root()
            require(directory(self.workspace, owned=True)._root_identity == self.workspace_boundary._root_identity,
                    'opening_workspace_changed', 6)
            require(stat.S_IMODE(self.workspace.lstat().st_mode) == 0o700,
                    'opening_workspace_not_private')
            require(set(os.listdir(self.workspace)) <= {'result.zip', 'code'},
                    'opening_workspace_foreign_content')
        if self.reference is not None:
            self.reference.verify_current()
            info = self.reference.path.lstat()
            require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600,
                    'opening_reference_not_private')
        if self.runtime is not None:
            self.runtime.load_api(required=('read_result_snapshot',))

    def _workspace(self):
        self.verify_current()
        descriptor = os.open(self.parent.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            require((os.fstat(descriptor).st_dev, os.fstat(descriptor).st_ino) == self.parent._root_identity,
                    'opening_workspace_parent_changed', 6)
            os.mkdir(self.workspace.name, mode=0o700, dir_fd=descriptor)
            self.effects['runtime_workspace'] = str(self.workspace)
            self.workspace_boundary = directory(self.workspace, owned=True)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self.verify_current()
        descriptor = os.open(self.workspace, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            require((os.fstat(descriptor).st_dev, os.fstat(descriptor).st_ino) == self.workspace_boundary._root_identity,
                    'opening_workspace_changed', 6)
            fd = os.open('result.zip', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
                         dir_fd=descriptor)
            try:
                raw = self.container.payloads['reference/result.zip']
                offset = 0
                while offset < len(raw):
                    count = os.write(fd, raw[offset:])
                    if count <= 0:
                        raise OSError('incomplete private reference write')
                    offset += count
                os.fsync(fd)
            finally:
                os.close(fd)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self.reference = PassiveFile(self.workspace / 'result.zip',
            expected_sha256=self.container.manifest['reference']['sha256'], limit=MAX_BYTES)

    def verify(self):
        require(self.snapshot is None and self.workspace_boundary is None, 'opening_already_started', 6)
        self._workspace()
        self.runtime = PatchHarborRuntime(self.pyz.path, trusted_artifact_sha256=self.pyz.sha256,
            workspace=self.workspace / 'code', safe_reference=True)
        self.runtime.load_api(required=('read_result_snapshot',))
        snapshot = self.runtime.read_snapshot(self.reference.path, expected_sha256=self.reference.sha256)
        expected = self.container.manifest['reference']
        require(binding(snapshot.context) == {k: expected[k] for k in binding(snapshot.context)}
                and snapshot.sha256 == self.reference.sha256, 'handoff_native_reference_binding', 3)
        member = reference_runtime_member(snapshot)
        with ZipFile(BytesIO(self.reference.raw)) as archive:
            require(archive.read(member) == self.pyz.raw, 'handoff_native_runtime_bytes')
        verify_projection(snapshot, self.container)
        self.verify_current()
        self.snapshot = snapshot
        return self.result('verify')

    def result(self, operation):
        require(self.snapshot is not None, 'opening_complete_verification_required', 6)
        return {'format_version': 'ai-runtime-' + operation + '-v1',
            'file': {'size': len(self.source.raw), 'sha256': self.source.sha256},
            'manifest': self.container.manifest, 'validation_scope': 'ai_runtime_outbound_complete',
            'container_verified': True, 'full_reference_valid': True, 'model_root_verified': True,
            'closure_verified': True, 'runtime_binding_verified': True,
            'external_hash_verified': self.expected_sha256 is not None,
            'runtime_source': 'standalone_pyz', 'runtime_workspace': str(self.workspace),
            'creator_authenticated': False, 'approval_granted': False,
            'full_semantic_validation': False, 'write_authorized': False}

    def extract(self):
        require(self.output is not None and self.snapshot is not None, 'opening_target_and_verification_required', 2)
        from ._sandbox_root import publish_sandbox
        self.verify_current()
        content, directories = publish_sandbox(self)
        self.verify_current()
        self.effects['bootstrap_state'] = 'complete'
        return {**self.result('extract'), 'sandbox_root': str(self.output),
            'project_root': str(self.output / 'project'), 'bootstrap_state': 'complete',
            'files': [{'path': name, 'size': len(raw), 'sha256': sha256(raw).hexdigest()}
                      for name, raw in sorted(content.items())], 'directories': sorted(directories)}
