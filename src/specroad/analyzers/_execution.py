"""Distribution-owned execution boundary; files cannot register executable code."""
from ._values import encoded
from .descriptors import AnalyzerDescriptor
from .registry import classify_descriptor
from .reports import create_report, subject_result
from .packages import create_package
from ._report_values import ENGINE_FACTS

def unavailable_package(request, *, run_ids=None):
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
            operational={'execution_supported': False, 'reason': reason},
            run_id=None if run_ids is None else run_ids[descriptor.data['analyzer_id']]))
    return create_package(request, reports)
