"""Explicit local host admission and native draft receipt; never Proposal apply."""
from hashlib import sha256
from io import BytesIO
import math
import os
from zipfile import ZipFile

from ..authoring._inspection_snapshot import InspectionSnapshot
from ..bundles.extraction import extract_bundle
from ..changes import PublicationAuthority
from ..proposals.values import ProposalOriginal
from ..storage.json_syntax import parse_json_object
from ._files import PassiveFile, absolute, directory, overlap, require
from ._export_boundary import binding, repository_root
from ._handoff import MAX_BYTES
from ._native_api import _api_call
from ._return_data import ReturnData
from ._return_draft import draft, publish
from ._return_channel import receiver_channel
from .opening import SandboxOpening


def _checked_contents(raw, inspection):
    """Read consumer bytes only after native inspection, matching its evidence."""
    require(inspection.package_sha256 == sha256(raw).hexdigest(), 'return_package_changed', 6)
    require(sum(e.size for e in inspection.entries) <= MAX_BYTES, 'return_package_limit')
    with ZipFile(BytesIO(raw)) as archive:
        result = {e.path: archive.read(e.path) for e in inspection.entries}
    require(all(len(result[e.path]) == e.size and sha256(result[e.path]).hexdigest() == e.sha256
                for e in inspection.entries), 'return_inspected_bytes_changed', 6)
    return result


class ReturnReceiver:
    def __init__(self, package, *, expected_sha256, reference, reference_sha256,
                 repository, workspace, patchharbor_pyz, patchharbor_pyz_sha256, authority, authorize_transport,
                 timeout=10800):
        require(type(authority) is PublicationAuthority, 'return_registered_host_authority_required', 2)
        require(callable(authorize_transport), 'return_transport_authority_required', 2)
        self.authorize_transport = authorize_transport
        require(type(timeout) in (int, float) and math.isfinite(timeout) and timeout > 0,
                'return_timeout_invalid', 2)
        self.authority, self.timeout = authority, timeout
        self.repository = directory(repository)
        self.source = PassiveFile(package, expected_sha256=expected_sha256, limit=MAX_BYTES)
        self.workspace = absolute(workspace)
        self.parent = directory(self.workspace.parent, owned=True)
        require(not overlap(self.workspace, self.repository.root) and not overlap(self.workspace, self.source.path),
                'return_host_workspace_overlap')
        require(not os.path.lexists(self.workspace), 'return_host_workspace_exists', 6)
        os.mkdir(self.workspace, 0o700)
        self.private = directory(self.workspace, owned=True)
        self.opening = SandboxOpening(reference, expected_sha256=reference_sha256,
            patchharbor_pyz=patchharbor_pyz, patchharbor_pyz_sha256=patchharbor_pyz_sha256,
            runtime_workspace=self.workspace / 'verification')
        self.data = self.api = self.project = self.snapshot = self.local_draft = None
        self.admitted = self.started = False
        self.completion = None

    def prepare(self):
        require(self.data is None, 'return_host_already_prepared', 6)
        self.opening.verify()
        self.api = self.opening.runtime.load_api(required=('inspect_patch', 'validate_patch', 'apply_guarded'))
        inspection = _api_call(self.api, self.api.inspect_patch, self.source.path)
        _api_call(self.api, self.api.validate_patch, self.source.path, reference_bundle=self.opening.reference.path)
        contents = _checked_contents(self.source.raw, inspection)
        prefix = inspection.entrypoint.rsplit('/', 1)[0]
        require(prefix.startswith('.specroad-return/') and prefix.count('/') == 1
                and len(prefix.split('/')[1]) == 64, 'return_stage_path_invalid')
        require(prefix + '/return.json' in contents and prefix + '/proposal.json' in contents,
                'return_data_missing', 3)
        manifest = parse_json_object(contents[prefix + '/return.json'])
        require(type(manifest.get('proposal')) is dict and type(manifest['proposal'].get('path')) is str,
                'return_proposal_binding_invalid', 3)
        original = ProposalOriginal(contents[prefix + '/proposal.json'], path=manifest['proposal']['path'])
        container = self.opening.container
        extract_bundle(container.project.source_bytes, self.workspace/'basis', expected_sha256=container.project.sha256)
        self.basis = InspectionSnapshot(self.workspace/'basis', None, include_archive_objects=True)
        data = ReturnData(container, original, self.basis.model)
        require(not data.no_changes and manifest == data.manifest, 'return_manifest_mismatch', 3)
        data.check_inspection(inspection)
        require({e.path: contents[e.path] for e in inspection.entries
                 if e.role.value not in ('manifest', 'handoff')} == dict(data.contents),
                'return_payload_mismatch')
        self.data = data
        self.local_draft = draft(original)
        project_path = container.manifest['project_path']
        self.project = directory(self.repository.root if project_path == '.' else self.repository.root/project_path)
        self.stage = self.repository.root/data.prefix
        self.verify_current()
        return self

    def verify_current(self):
        self.repository._check_root(); self.parent._check_root(); self.private._check_root()
        self.source.verify_current(); self.opening.verify_current()
        if self.project is not None:
            self.project._check_root(); self.basis.verify_current()

    def _fresh_stage(self):
        parent = self.stage.parent
        if os.path.lexists(parent):
            directory(parent, owned=True)
        require(not os.path.lexists(self.stage), 'return_stage_collision', 6)

    def _admit(self, facts):
        self.verify_current()
        require(not self.admitted and facts.inspection.package_sha256 == self.source.sha256,
                'return_admission_repeated_or_changed')
        self.data.check_inspection(facts.inspection)
        require({e.path: facts.contents[e.path] for e in facts.inspection.entries
                 if e.role.value not in ('manifest', 'handoff')} == dict(self.data.contents),
                'return_admission_payload_changed')
        require(repository_root(facts.context) == self.repository.root
                and binding(facts.context) == {k:self.data.manifest['reference'][k] for k in binding(facts.context)},
                'return_host_binding_changed', 6)
        self._fresh_stage()
        self.snapshot = InspectionSnapshot(self.project.root, None, include_archive_objects=True)
        require(self.snapshot.raw == self.basis.raw,
                'return_host_project_changed', 6)
        require(self.snapshot.source.configuration.project_id == self.data.manifest['project_id'],
                'return_host_project_identity_changed', 6)
        self.snapshot.verify_current()
        allowed = self.authorize_transport({'package_sha256': self.source.sha256,
            'repository': str(self.repository.root), 'reference': self.data.manifest['reference'],
            'project_id': self.data.manifest['project_id'], 'proposal': self.data.manifest['proposal']})
        require(type(allowed) is bool and allowed, 'return_transport_not_authorized')
        self.verify_current(); self.snapshot.verify_current(); self._fresh_stage()
        self.admitted = True
        return True

    def _receive(self):
        require(self.admitted, 'return_host_admission_missing')
        self.verify_current()
        self.snapshot.verify_current()
        for name, raw in self.data.contents.items():
            if name == self.data.entrypoint:
                continue  # PatchHarbor executes its captured private script, not a payload copy.
            require(PassiveFile(self.repository.root/name, limit=MAX_BYTES).raw == raw,
                    'return_staged_bytes_changed', 6)
        self.completion = publish(self.snapshot.model, self.local_draft, authority=self.authority,
            transaction_id='return-' + self.data.manifest['return_id'])
        require(self.completion['write_state'] == 'committed' and not self.completion['no_change'],
                'return_draft_not_committed', 6)
        return self.completion

    def receive(self):
        require(not self.started, 'return_host_already_started', 6)
        self.started = True
        if self.data is None: self.prepare()
        self.verify_current(); self._fresh_stage()
        _api_call(self.api, self.api.validate_patch, self.source.path, repository=self.repository.root)
        with receiver_channel(self._receive, self.timeout) as outcome:
            report = _api_call(self.api, self.api.apply_guarded, self.source.path,
                expected_sha256=self.source.sha256, expected_repository=self.repository.root,
                admission=self._admit, output_directory=self.workspace, timeout=self.timeout)
        return {'status': 'proposal_received' if self.completion is not None else 'failed',
            'proposal_id': self.local_draft.binding.proposal_id, 'package_sha256': self.source.sha256,
            'draft_completion': self.completion, 'replayed': False, 'applied': False,
            'approval_granted': False, 'patchharbor': {'success': report.success,
                'process_exit_code': report.process_exit_code, 'primary_result': report.primary_result.kind.value,
                'result_status': report.result_bundle.status.value,
                'result_path': None if report.result_bundle.path is None else str(report.result_bundle.path)},
            'receiver_failure': None if outcome['error'] is None else getattr(outcome['error'], 'reason', 'return_host_failed')}
