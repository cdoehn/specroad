"""Pinned distribution facts; describing them never imports transport code."""

import re


VERSION = '1.6.0'
ARTIFACT_SHA256 = '377e715d7cb443eb5e80a3e7f9e8405f36092a0f7c062745b70c8b3a2e3eb055'
PYTHONS = ((3, 10), (3, 11), (3, 12), (3, 13), (3, 14))
REQUIRES_PYTHON = '>=3.10'
OPERATIONS = ('bundle', 'inspect_patch', 'validate_patch', 'pack_patch', 'apply',
              'integration_capabilities', 'read_result_snapshot')


def valid_digest(value):
    """Both runtime trust and passive Result inputs require a complete digest."""
    return type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def describe_distribution(source_sha256, *, loaded):
    """Return fresh contract values, without asserting validation or acceptance."""
    return {
        'distribution': 'patchharbor', 'version': VERSION,
        'artifact_sha256': ARTIFACT_SHA256,
        'profile': 'patchharbor-core-no-watcher-v1',
        'runtime_profile': 'python-present', 'requires_python': REQUIRES_PYTHON,
        'supported_cpython': ['%d.%d' % pair for pair in PYTHONS],
        'platform_profiles': ['linux-x86_64'],
        'source_result_sha256': source_sha256,
        'api_capabilities': {name: True for name in OPERATIONS},
        'unavailable_capabilities': [],
        'integration_contract_version': 1,
        'snapshot_contract_version': 1,
        'runtime_loaded': loaded,
        'capability_scope': 'pinned_distribution_contract',
        'full_reference_valid': False,
    }
