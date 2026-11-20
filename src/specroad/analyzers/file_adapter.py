"""Passive file values and unavailable execution; no plugin/model discovery."""
from ._values import decode, encoded, require, shape, digest, extensions, hash_value
from .descriptors import AnalyzerDescriptor
from .registry import builtin_descriptor
from .requests import analyzer_binding
from ._request_values import RESOURCE_ID
from ._text_policy import validate_minimum


def default_inputs(configuration):
    descriptor = builtin_descriptor()
    policy = dict(adapter='specroad.py3langid', adapter_version='1.0.0', mismatch='warning',
        undetermined='info', compatible_coarse='info', unverifiable='info',
        min_text_codepoints=20, min_score='0.900000000000', min_margin='0.100000000000')
    configured = configuration.get('analyzer_policy', {}).get('language_detection', {})
    require(type(configured) is dict, 'analyzer_policy_object_required')
    policy.update(configured)
    validate_minimum(policy['min_text_codepoints'])
    return dict(analyzers=[analyzer_binding(descriptor, ['language_detection'])],
        settings={'specroad.py3langid': {'language_detection': policy}}, context=[], extensions={})


def request_inputs(raw, selected):
    """Bind exactly the requested analyzer set, never silently filter a profile."""
    value = validate_inputs(raw)
    require(type(value['analyzers']) is list and bool(value['analyzers']), 'analyzer_inputs_required')
    names = []
    for item in value['analyzers']:
        shape(item, ('descriptor', 'descriptor_sha256', 'capabilities'))
        descriptor = AnalyzerDescriptor(encoded(item['descriptor']))
        require(descriptor.sha256 == item['descriptor_sha256'], 'analyzer_descriptor_hash_mismatch')
        descriptor.select_capabilities(item['capabilities'])
        names.append(descriptor.data['analyzer_id'])
    require(names == sorted(set(names)), 'analyzer_sorted_unique_required')
    require(len(selected) == len(set(selected)) and sorted(selected) == names,
        'analyzer_selection_inputs_mismatch', exit_code=2)
    # Full settings/context validation remains in the shared request validator.
    return value


def descriptors(raw=None):
    known = builtin_descriptor()
    found = {known.data['analyzer_id']: known}
    if raw is not None:
        value = validate_inputs(raw)
        require(type(value['analyzers']) is list and bool(value['analyzers']), 'analyzer_inputs_required')
        for item in value['analyzers']:
            shape(item, ('descriptor','descriptor_sha256','capabilities'))
            descriptor = AnalyzerDescriptor(encoded(item['descriptor']))
            require(descriptor.sha256 == item['descriptor_sha256'], 'analyzer_descriptor_hash_mismatch')
            descriptor.select_capabilities(item['capabilities'])
            name = descriptor.data['analyzer_id']
            require(name not in found or found[name].canonical_bytes == descriptor.canonical_bytes,
                'analyzer_descriptor_identity_conflict', exit_code=6)
            found[name] = descriptor
    return tuple(found[name] for name in sorted(found))




def validate_inputs(raw):
    value = decode(raw)
    shape(value, ('analyzers','settings','context','extensions'))
    require(type(value['analyzers']) is list and bool(value['analyzers']), 'analyzer_inputs_required')
    names = []
    for item in value['analyzers']:
        shape(item, ('descriptor','descriptor_sha256','capabilities'))
        descriptor = AnalyzerDescriptor(encoded(item['descriptor']))
        require(descriptor.sha256 == item['descriptor_sha256'], 'analyzer_descriptor_hash_mismatch')
        descriptor.select_capabilities(item['capabilities'])
        names.append(descriptor.data['analyzer_id'])
    require(names == sorted(set(names)), 'analyzer_sorted_unique_required')
    require(type(value['settings']) is dict and set(value['settings']) == set(names)
            and all(type(v) is dict for v in value['settings'].values()), 'analyzer_settings_binding_mismatch')
    require(type(value['context']) is list, 'analyzer_context_array_required')
    resources = []
    for item in value['context']:
        shape(item, ('resource_id','sha256','value'))
        require(type(item['resource_id']) is str and RESOURCE_ID.fullmatch(item['resource_id']) is not None,
            'analyzer_invalid_resource_id')
        hash_value(item['sha256'], '/context/sha256')
        require(item['sha256'] == digest(item['value']), 'analyzer_context_hash_mismatch')
        resources.append(item['resource_id'])
    require(resources == sorted(set(resources)), 'analyzer_sorted_unique_required')
    extensions(value['extensions'])
    return value

from ._execution import unavailable_package
__all__ = ('default_inputs','request_inputs','descriptors','validate_inputs','unavailable_package')
