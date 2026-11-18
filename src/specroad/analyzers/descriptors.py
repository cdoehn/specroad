"""Closed analyzer descriptors are data, never executable registration."""
from dataclasses import dataclass
from hashlib import sha256

from ..profiles._contract import SEMVER
from ._values import decode, encoded, extensions, hash_value, identifier, require, shape, tokens

DESCRIPTOR_FIELDS = frozenset({'contract_version', 'analyzer_id', 'adapter_version',
    'capabilities', 'subject_modes', 'result_schema_version', 'execution_mode',
    'determinism', 'dependency_requirements', 'extensions'})


def _validate(value):
    shape(value, DESCRIPTOR_FIELDS)
    require(value['contract_version'] == '1.0.0', 'analyzer_unsupported_contract', '/contract_version')
    for field in ('adapter_version', 'result_schema_version'):
        require(type(value[field]) is str and SEMVER.fullmatch(value[field]) is not None,
                'analyzer_invalid_version', '/' + field)
    identifier(value['analyzer_id'], '/analyzer_id')
    tokens(value['capabilities'], '/capabilities')
    tokens(value['subject_modes'], '/subject_modes', allowed=('single_text', 'multi_subject', 'structured'))
    require(value['execution_mode'] in ('builtin_worker', 'external_result_only', 'future_unsupported'),
            'analyzer_invalid_execution_mode', '/execution_mode')
    require(value['determinism'] in ('pinned_engine', 'not_guaranteed'),
            'analyzer_invalid_determinism', '/determinism')
    dependencies = value['dependency_requirements']
    require(type(dependencies) is list, 'analyzer_array_required', '/dependency_requirements')
    names = []
    for index, entry in enumerate(dependencies):
        at = '/dependency_requirements/' + str(index)
        shape(entry, ('name', 'requirement'), at)
        identifier(entry['name'], at + '/name')
        text = entry['requirement']
        require(type(text) is str and bool(text) and text == text.strip()
                and not any(ord(c) < 32 or ord(c) == 127 for c in text),
                'analyzer_invalid_dependency_requirement', at + '/requirement')
        names.append(entry['name'])
    require(names == sorted(set(names)), 'analyzer_sorted_unique_required', '/dependency_requirements')
    extensions(value['extensions'])


@dataclass(frozen=True, init=False)
class AnalyzerDescriptor:
    """Own canonical values; reads return fresh data without granting execution."""
    _encoded: bytes

    def __init__(self, raw):
        value = decode(raw)
        _validate(value)
        object.__setattr__(self, '_encoded', encoded(value))

    def require_binding(self, *, analyzer_id, adapter_version, descriptor_sha256):
        identifier(analyzer_id, '/analyzer_id')
        require(type(adapter_version) is str and SEMVER.fullmatch(adapter_version) is not None,
                'analyzer_invalid_version', '/adapter_version')
        hash_value(descriptor_sha256, '/descriptor_sha256')
        value = self.data
        require(analyzer_id == value['analyzer_id'], 'analyzer_identity_mismatch', exit_code=6)
        require(adapter_version == value['adapter_version'], 'analyzer_version_mismatch', exit_code=6)
        require(descriptor_sha256 == self.sha256, 'analyzer_descriptor_mismatch', exit_code=6)

    def select_capabilities(self, capabilities):
        tokens(capabilities, '/capabilities', allowed=self.data['capabilities'])
        return tuple(capabilities)

    @property
    def data(self):
        return decode(self._encoded)

    @property
    def canonical_bytes(self):
        return self._encoded

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()


def builtin_descriptor():
    """Declared shipped identity; worker installation is a separate capability."""
    return AnalyzerDescriptor(encoded({'contract_version': '1.0.0', 'analyzer_id': 'specroad.py3langid',
        'adapter_version': '1.0.0', 'capabilities': ['language_detection'], 'subject_modes': ['single_text'],
        'result_schema_version': '1.0.0', 'execution_mode': 'builtin_worker', 'determinism': 'pinned_engine',
        'dependency_requirements': [{'name': 'numpy', 'requirement': '*'},
            {'name': 'py3langid', 'requirement': '==0.4.0'}, {'name': 'python', 'requirement': '>=3.10'}],
        'extensions': {}}))


def classify_descriptor(descriptor):
    require(type(descriptor) is AnalyzerDescriptor, 'analyzer_descriptor_required', exit_code=2)
    known = descriptor.canonical_bytes == builtin_descriptor().canonical_bytes
    # No worker is implemented at this plan position. An imported flag, even
    # an exact descriptor copy, cannot authorize importing or starting one.
    return {'known_builtin': known, 'descriptor_sha256': descriptor.sha256,
            'execution_supported': False, 'availability': 'not_implemented' if known else 'external_result_only'}

__all__ = ('AnalyzerDescriptor', 'builtin_descriptor', 'classify_descriptor')
