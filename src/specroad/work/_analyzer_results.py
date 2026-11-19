"""Retained subject observations and bound engine metadata, never fake success."""
from ..analyzers._values import encoded
from ..analyzers.descriptors import AnalyzerDescriptor
from ..analyzers.registry import classify_descriptor
from ..analyzers.reports import subject_result, create_report
from ..analyzers.packages import create_package, ReportPackage
from ..analyzers._report_values import ENGINE_FACTS, engine_values
from ._data_contract import _require, _object


def engines(request):
    result = []
    for item in request.data['analyzers']:
        descriptor = AnalyzerDescriptor(encoded(item['descriptor']))
        reason = classify_descriptor(descriptor)['availability']
        result.append(dict(analyzer_id=descriptor.data['analyzer_id'],
            engine=dict(adapter_version=descriptor.data['adapter_version'],
                **{name:{'value':None,'reason':reason} for name in ENGINE_FACTS}), reason=reason))
    return result


def check_engines(request, rows):
    _require(type(rows) is list and len(rows)==len(request.data['analyzers']))
    for item, row in zip(request.data['analyzers'], rows):
        _object(row, ('analyzer_id','engine','reason'))
        _require(row['analyzer_id']==item['descriptor']['analyzer_id']
            and row['reason'] in ('not_implemented','external_result_only'))
        engine_values(row['engine'],item)
        _require(row['engine']==dict(adapter_version=item['descriptor']['adapter_version'],
            **{name:{'value':None,'reason':row['reason']} for name in ENGINE_FACTS}))


def observation(subject):
    # Completion of this technical unit is not linguistic completion. Honest
    # open coverage is retained and reused; installed worker integration follows.
    return subject_result(subject,status='open',payload={})


def pair_units(request):
    return [dict(key='subject:'+item['descriptor_sha256']+':'+subject['subject_key'],phase='subjects',
        range={'analyzer_id':item['descriptor']['analyzer_id'],
            'descriptor_sha256':item['descriptor_sha256'],'subject_key':subject['subject_key']})
        for item in request.data['analyzers'] for subject in request.data['subjects']]


def collect_results(request, done, engine_rows, *, run_ids=None):
    reports=[]
    for binding, engine in zip(request.data['analyzers'],engine_rows):
        rows=[done['subject:'+binding['descriptor_sha256']+':'+s['subject_key']]
              for s in request.data['subjects']]
        reports.append(create_report(request,analyzer_id=engine['analyzer_id'],engine=engine['engine'],
            subjects=sorted(rows,key=lambda s:s['subject_key']),run_status='unavailable',
            operational={'execution_supported':False,'reason':engine['reason']},
            run_id=None if run_ids is None else run_ids[engine['analyzer_id']]))
    return create_package(request,reports)


def final_result(request, command_id, done, *, document=None):
    if command_id=='analyzer.request': return request
    run_ids=None
    if document is not None:
        package=ReportPackage(encoded(document),request=request)
        run_ids={r.data['analyzer']['descriptor']['analyzer_id']:r.data['run_id'] for r in package.reports}
    return collect_results(request,done,done['snapshot']['engines'],run_ids=run_ids)


def prepare_subject(request, task):
    subject = next(s for s in request.data['subjects'] if s['subject_key']==task['range']['subject_key'])
    return observation(subject)
