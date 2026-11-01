"""Closed W.2.1 manifest and canonical outer ZIP; inner archives stay unchanged."""
from hashlib import sha256

from ..model.canonical import canonical_json_bytes
from ..storage.archive import encode_zip, decode_zip, validate_portable_archive_paths
from ..storage.json_syntax import parse_json_object
from . import _contract
from ._files import require
from ._export_boundary import binding


FORMAT = 'specroad-ai-handoff-v1'
MAX_BYTES = 512 * 1024 * 1024


class OutboundContainer:
    def __init__(self, project, result, snapshot, core, core_identity, project_path):
        runtime = snapshot.runtime
        require(runtime.status == 'embedded' and runtime.version == _contract.SAFE_VERSION
                and runtime.artifact_sha256 == _contract.SAFE_ARTIFACT_SHA256
                and runtime.requires_python == _contract.REQUIRES_PYTHON
                and runtime.profile == 'patchharbor-core-no-watcher-v1', 'reference_runtime_mismatch')
        require(snapshot.sha256 == result.sha256, 'reference_bytes_changed', 6)
        require(project_path == '.' or (project_path and not project_path.startswith('/')),
                'transport_project_path_invalid')
        if project_path != '.':
            validate_portable_archive_paths([project_path])
        m = project.manifest
        require(m['bundle_kind'] == 'project' and m['scope_descriptor']['scope_kind'] == 'project'
                and m['scope_descriptor']['configuration_id'] is None and m['read_only'] is False
                and m['idempotency_scope'] == 'portable'
                and m['origin_model_root_sha256'] == m['bundle_model_root_sha256'],
                'transport_project_not_closed')
        payloads = {'runtime/specroad.pyz': core.raw, 'reference/result.zip': result.raw,
                    'project/project.zip': project.source_bytes}
        manifest = {'format_version': FORMAT, 'direction': 'outbound',
            'runtime_profile': 'python-present', 'project_id': m['project_id'],
            'project_path': project_path, 'scope_descriptor': m['scope_descriptor'],
            'model_root_sha256': m['bundle_model_root_sha256'],
            'reference': {'path': 'reference/result.zip', 'sha256': result.sha256, **binding(snapshot.context)},
            'runtimes': {'specroad': core_identity, 'patchharbor': {
                'path': 'reference/result.zip',
                # The native Result reader has validated the complete runtime
                # descriptor. Bootstrap assess returns its exact member name;
                # no second PH format validator or Result interpreter is used.
                'member_path': result.runtime_member,
                'tool_version': runtime.version, 'artifact_sha256': runtime.artifact_sha256,
                'requires_python': runtime.requires_python, 'distribution_profile': runtime.profile,
                'supported_cpython': ['3.10', '3.11', '3.12', '3.13', '3.14'],
                'platform_profile': 'linux-x86_64', 'integration_contract_version': 1,
                'snapshot_contract_version': 1}},
            'entries': [{'path': name, 'size': len(raw), 'sha256': sha256(raw).hexdigest()}
                        for name, raw in sorted(payloads.items())]}
        manifest['package_id'] = sha256(FORMAT.encode() + b'\0' + canonical_json_bytes(manifest)).hexdigest()
        entries = {'handoff.json': canonical_json_bytes(manifest), **payloads}
        raw = encode_zip(entries, max_uncompressed_bytes=MAX_BYTES)
        checked = decode_zip(raw, max_uncompressed_bytes=MAX_BYTES,
                             validate_paths=validate_portable_archive_paths)
        require(checked == entries and parse_json_object(checked['handoff.json']) == manifest,
                'transport_container_binding_failed', 3)
        self.source_bytes, self.manifest = raw, manifest
        self.sha256 = sha256(raw).hexdigest()
