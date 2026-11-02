"""Passive closed handoff verification, independent of Runtime loading or writes."""
from hashlib import sha256
import re
from uuid import UUID

from ..bundles.container import BundleContainer
from ..bundles.verification import verify_bundle
from ..model.canonical import canonical_json_bytes
from ..storage.archive import decode_zip, validate_portable_archive_paths
from ..storage.json_syntax import parse_json_object
from . import _contract
from ._core_artifact import core_identity
from ._files import require
from ._handoff import FORMAT, MAX_BYTES


def _reference(value, raw):
    require(type(value) is dict and set(value) == {'path', 'sha256', 'repo_id',
        'base_commit', 'state_fingerprint', 'fingerprint_algorithm'}, 'handoff_reference_fields', 3)
    require(all(type(v) is str for v in value.values()), 'handoff_reference_types', 3)
    try:
        repo = UUID(value['repo_id'])
    except ValueError as error:
        from .snapshots import TransportFailure
        raise TransportFailure(3, reason='handoff_repository_id') from error
    require(str(repo) == value['repo_id'] and repo.version == 4
        and re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}', value['base_commit']) is not None
        and re.fullmatch('[0-9a-f]{16}', value['state_fingerprint']) is not None
        and value['fingerprint_algorithm'] == 'patchharbor-state-v1'
        and value['path'] == 'reference/result.zip'
        and value['sha256'] == sha256(raw).hexdigest(), 'handoff_reference_binding', 3)
    return dict(value)


class OpeningContainer:
    def __init__(self, raw):
        payloads = decode_zip(raw, max_uncompressed_bytes=MAX_BYTES,
                             validate_paths=validate_portable_archive_paths)
        require(set(payloads) == {'handoff.json', 'runtime/specroad.pyz',
            'reference/result.zip', 'project/project.zip'}, 'handoff_members', 3)
        manifest = parse_json_object(payloads.pop('handoff.json'))
        require(set(manifest) == {'format_version', 'package_id', 'direction', 'runtime_profile',
            'project_id', 'project_path', 'scope_descriptor', 'model_root_sha256',
            'reference', 'runtimes', 'entries'}, 'handoff_fields', 3)
        project_path = manifest['project_path']
        require(type(project_path) is str and bool(project_path), 'handoff_project_path', 3)
        if project_path != '.':
            validate_portable_archive_paths([project_path])
        project = BundleContainer(payloads['project/project.zip'])
        m = project.manifest
        require(m['bundle_kind'] == 'project' and m['read_only'] is False
            and m['idempotency_scope'] == 'portable' and m['scope_descriptor']['scope_kind'] == 'project'
            and m['scope_descriptor']['configuration_id'] is None
            and m['origin_model_root_sha256'] == m['bundle_model_root_sha256'],
            'handoff_project_not_closed', 7)
        verify_bundle(project.source_bytes, expected_sha256=project.sha256)
        identity = core_identity(payloads['runtime/specroad.pyz'])
        expected = {'format_version': FORMAT, 'direction': 'outbound', 'runtime_profile': 'python-present',
            'project_id': m['project_id'], 'project_path': project_path,
            'scope_descriptor': m['scope_descriptor'], 'model_root_sha256': m['bundle_model_root_sha256'],
            'reference': _reference(manifest['reference'], payloads['reference/result.zip']),
            'runtimes': {'specroad': identity, 'patchharbor': {
                'path': 'reference/result.zip', 'member_path': 'runtime/' + _contract.ARTIFACT_FILENAME,
                'tool_version': _contract.VERSION, 'artifact_sha256': _contract.ARTIFACT_SHA256,
                'requires_python': _contract.REQUIRES_PYTHON, 'distribution_profile': _contract.PROFILE,
                'supported_cpython': ['3.10', '3.11', '3.12', '3.13', '3.14'],
                'platform_profile': 'linux-x86_64', 'integration_contract_version': 1,
                'snapshot_contract_version': 1}},
            'entries': [{'path': name, 'size': len(content), 'sha256': sha256(content).hexdigest()}
                        for name, content in sorted(payloads.items())]}
        expected['package_id'] = sha256(FORMAT.encode() + b'\0' + canonical_json_bytes(expected)).hexdigest()
        # Canonical bytes also distinguish JSON booleans from integer 0/1.
        require(canonical_json_bytes(manifest) == canonical_json_bytes(expected), 'handoff_manifest_binding', 3)
        original = decode_zip(raw, max_uncompressed_bytes=MAX_BYTES,
                              validate_paths=validate_portable_archive_paths)['handoff.json']
        require(original == canonical_json_bytes(expected), 'handoff_manifest_noncanonical', 3)
        self.raw, self.sha256 = raw, sha256(raw).hexdigest()
        self.payloads, self.manifest, self.project = payloads, expected, project
