"""Pinned distribution facts; describing them never imports transport code."""

import re


VERSION = '1.8.0'
ARTIFACT_SHA256 = '050cc2d1dc3ecbb1478f6a40c9a5123d1d34d350215d5cc0303025ea08dc4f1e'
PYTHONS = ((3, 10), (3, 11), (3, 12), (3, 13), (3, 14))
REQUIRES_PYTHON = '>=3.10'
PROFILE = 'patchharbor-core-no-watcher-v1'
ARTIFACT_FILENAME = 'patchharbor-1.8.0.pyz'
ARTIFACT_SIZE = 1049613
MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
CONTENT_ID = 'f144df901034f6dd6b3211a2a6b5e613646fa1afb2f7ce19c75862a7a4c4bf21'
SOURCE_COMMIT = '2121d3abd2ca4b6c523d9e0698d997a86581d5bc'
SAFE_OPERATIONS = ('context', 'prepare_reference_export', 'repositories', 'configuration')
OPERATIONS = ('bundle', 'inspect_patch', 'validate_patch', 'pack_patch', 'apply',
              'integration_capabilities', 'read_result_snapshot', 'export_runtime')


def valid_digest(value):
    """Both runtime trust and passive Result inputs require a complete digest."""
    return type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def describe_distribution(source_sha256, *, loaded):
    """Return fresh contract values, without asserting validation or acceptance."""
    return {
        'distribution': 'patchharbor', 'version': VERSION,
        'artifact_sha256': ARTIFACT_SHA256,
        'profile': PROFILE,
        'artifact_size': ARTIFACT_SIZE, 'content_id': CONTENT_ID, 'source_commit': SOURCE_COMMIT,
        'runtime_profile': 'python-present', 'requires_python': REQUIRES_PYTHON,
        'supported_cpython': ['%d.%d' % pair for pair in PYTHONS],
        'platform_profiles': ['linux-x86_64'],
        'source_artifact_sha256': source_sha256,
        'runtime_source': 'standalone_pyz',
        'api_capabilities': {name: True for name in OPERATIONS},
        'unavailable_capabilities': [],
        'integration_contract_version': 1,
        'snapshot_contract_version': 1,
        'guarded_apply_contract_version': 1,
        'runtime_loaded': loaded,
        'capability_scope': 'pinned_distribution_contract',
        'full_reference_valid': False,
    }
