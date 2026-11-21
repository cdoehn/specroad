"""Distribution-owned descriptor registry; external data cannot register execution."""
from .descriptors import AnalyzerDescriptor
from ._values import encoded, require


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
    # This is passive capability metadata, never dependency availability or
    # authority to run. Only explicit execution enters the trusted worker.
    return {'known_builtin': known, 'descriptor_sha256': descriptor.sha256,
            'execution_supported': known, 'availability': 'not_checked' if known else 'external_result_only'}
