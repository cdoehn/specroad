"""Passive file values and unavailable execution; no plugin/model discovery."""
from ._values import decode, encoded, require, shape
from .descriptors import AnalyzerDescriptor
from .registry import builtin_descriptor, classify_descriptor
from .requests import analyzer_binding
from .reports import create_report, subject_result
from .packages import create_package
from ._report_values import ENGINE_FACTS


def default_inputs(configuration):
    descriptor = builtin_descriptor()
    policy = dict(adapter='specroad.py3langid', adapter_version='1.0.0', mismatch='warning',
        undetermined='info', compatible_coarse='info', unverifiable='info',
        min_text_codepoints=20, min_score='0.900000000000', min_margin='0.100000000000')
    configured = configuration.get('analyzer_policy', {}).get('language_detection', {})
    require(type(configured) is dict, 'analyzer_policy_object_required')
    policy.update(configured)
    return dict(analyzers=[analyzer_binding(descriptor, ['language_detection'])],
        settings={'specroad.py3langid': {'language_detection': policy}}, context=[], extensions={})


def request_inputs(raw, selected):
    """Bind exactly the requested analyzer set, never silently filter a profile."""
    value = decode(raw)
    shape(value, ('analyzers', 'settings', 'context', 'extensions'))
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
        value = decode(raw)
        shape(value, ('analyzers', 'settings', 'context', 'extensions'))
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


def unavailable_package(request):
    """Truthful full coverage until the separately planned worker is installed."""
    reports = []
    for entry in request.data['analyzers']:
        descriptor = AnalyzerDescriptor(encoded(entry['descriptor']))
        availability = classify_descriptor(descriptor)
        reason = availability['availability']
        engine = dict(adapter_version=descriptor.data['adapter_version'],
            **{name: {'value': None, 'reason': reason} for name in ENGINE_FACTS})
        subjects = sorted((subject_result(s, status='open', payload={})
                           for s in request.data['subjects']), key=lambda s: s['subject_key'])
        reports.append(create_report(request, analyzer_id=descriptor.data['analyzer_id'],
            engine=engine, subjects=subjects, run_status='unavailable',
            operational={'execution_supported': False, 'reason': reason}))
    return create_package(request, reports)
