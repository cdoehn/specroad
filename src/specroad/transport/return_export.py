"""Python-only preparation of exactly one native reference-bound return ZIP."""
from hashlib import sha256
import os
from pathlib import Path
import tempfile

from ..authoring._inspection_snapshot import InspectionSnapshot
from ..bundles.extraction import extract_bundle
from ..proposals._validation_input import ProposalInput
from ._files import directory, overlap, require, PassiveFile
from ._handoff import MAX_BYTES
from ._return_data import ReturnData
from .opening import SandboxOpening
from .outbound import _api_call


def _write_contents(root, contents, entrypoint):
    """Exclusive files in a fresh host-owned directory; paths are generated."""
    os.mkdir(root, 0o700)
    for name, raw in sorted(contents.items()):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o755 if name == entrypoint else 0o644)
        try:
            with os.fdopen(fd, 'wb', closefd=False) as stream:
                stream.write(raw); stream.flush(); os.fsync(fd)
        finally:
            os.close(fd)


class ReturnExport:
    def __init__(self, project, *, reference, reference_sha256, proposal,
                 patchharbor_pyz, patchharbor_pyz_sha256, output_root, output):
        from ..model.paths import project_path
        self.project = directory(project)
        self.output = directory(output_root, owned=True)
        require(not overlap(self.project.root, self.output.root), 'return_output_inside_project')
        project_path(output)
        self.destination = self.output.root / output
        require(not os.path.lexists(self.destination), 'return_output_exists', 6)
        # Reject malformed input/overlap before creating the private workspace.
        source = PassiveFile(reference, expected_sha256=reference_sha256, limit=MAX_BYTES)
        require(not overlap(self.destination, source.path), 'return_reference_output_overlap')
        self.snapshot = InspectionSnapshot(self.project.root, None, include_archive_objects=True)
        self.supplied = ProposalInput(self.snapshot.source, proposal, self.project.root)
        self.original = self.supplied.original()
        self.workspace = Path(tempfile.mkdtemp(prefix='.specroad-return-', dir=self.output.root))
        self.opening = SandboxOpening(source.path, expected_sha256=source.sha256,
            patchharbor_pyz=patchharbor_pyz, patchharbor_pyz_sha256=patchharbor_pyz_sha256,
            runtime_workspace=self.workspace / 'verification')
        self.data = None

    def prepare(self):
        self.opening.verify()
        container = self.opening.container
        require(self.snapshot.source.configuration.project_id == container.manifest['project_id'],
                'return_project_identity_mismatch', 6)
        extract_bundle(container.project.source_bytes, self.workspace / 'basis',
                       expected_sha256=container.project.sha256)
        self.basis = InspectionSnapshot(self.workspace / 'basis', None, include_archive_objects=True)
        current = dict(self.snapshot.raw)
        if self.original.path in current:
            require(current.pop(self.original.path) == self.original.source_bytes, 'return_proposal_input_mismatch', 6)
        require(current == self.basis.raw, 'return_delta_outside_proposal', 6)
        self.data = ReturnData(container, self.original, self.basis.model)
        self.verify_current()
        return self.data

    def verify_current(self):
        self.project._check_root(); self.output._check_root()
        self.opening.verify_current(); self.snapshot.verify_current(); self.supplied.verify_current()
        if hasattr(self, 'basis'):
            self.basis.verify_current()

    def execute(self):
        data = self.data if self.data is not None else self.prepare()
        self.verify_current()
        common = {'format_version': 'proposal-return-export-v1', 'manifest': data.manifest,
            'normative': False, 'approval_granted': False, 'write_authorized': False,
            'full_semantic_validation': False, 'source_bytes_rechecked': True}
        if data.no_changes:
            return {**common, 'status': 'no_changes', 'generated': False, 'file': None}
        content = self.workspace / 'contents'
        _write_contents(content, data.contents, data.entrypoint)
        api = self.opening.runtime.load_api(required=('pack_patch', 'inspect_patch', 'validate_patch'))
        self.verify_current()
        result = _api_call(api, api.pack_patch, content, reference_bundle=self.opening.reference.path,
            entrypoint=data.entrypoint, output=self.destination,
            modes={name: 0o755 if name == data.entrypoint else 0o644 for name in data.contents})
        data.check_inspection(_api_call(api, api.inspect_patch, result.path))
        checked = _api_call(api, api.validate_patch, result.path, reference_bundle=self.opening.reference.path)
        require(checked.binding_matches is True and checked.reference_sha256 == self.opening.reference.sha256,
                'return_native_reference_mismatch', 6)
        self.verify_current()
        produced = PassiveFile(result.path, limit=MAX_BYTES)
        require(produced.sha256 == checked.inspection.package_sha256, 'return_output_changed', 6)
        return {**common, 'status': 'created', 'generated': True,
            'file': {'path': str(result.path), 'size': len(produced.raw), 'sha256': sha256(produced.raw).hexdigest()}}
