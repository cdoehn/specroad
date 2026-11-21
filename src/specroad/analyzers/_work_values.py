"""Closed inert subject/engine values shared by worker and durable Work."""
from ._values import digest, encoded, require, shape
from ._report_values import (ENGINE_FACTS, engine_values, report_subjects,
                             check_findings, exact_coverage)
from .reports import create_report
from .packages import create_package, ReportPackage

from ._work_observations import check_language_unit

CHANNEL = 'analyzer-work-channel-v1'


def static_engines(request, reason='not_requested'):
    return [dict(analyzer_id=e['descriptor']['analyzer_id'],
        engine=dict(adapter_version=e['descriptor']['adapter_version'],
            **{k:dict(value=None, reason=reason) for k in ENGINE_FACTS}),
        inventory=dict(runtime=None, numpy=None), reason=reason)
        for e in request.data['analyzers']]


def check_engines(request, rows):
    require(type(rows) is list and len(rows) == len(request.data['analyzers']),
            'analyzer_work_engines', exit_code=5)
    for entry, row in zip(request.data['analyzers'], rows):
        shape(row, ('analyzer_id', 'engine', 'inventory', 'reason'))
        require(row['analyzer_id'] == entry['descriptor']['analyzer_id']
            and (row['reason'] is None or type(row['reason']) is str and bool(row['reason'])),
            'analyzer_work_engine_binding', exit_code=5)
        engine_values(row['engine'], entry)
        shape(row['inventory'], ('runtime', 'numpy'))
        for name in ('runtime', 'numpy'):
            inventory = row['inventory'][name]
            require(inventory is None or type(inventory) is dict,
                    'analyzer_work_inventory', exit_code=5)
            require(row['engine'][name + '_fingerprint']['value'] ==
                    (None if inventory is None else digest(inventory)),
                    'analyzer_work_inventory_binding', exit_code=5)


def select(request, pair):
    shape(pair, ('analyzer_id', 'descriptor_sha256', 'subject_key'))
    entries = [e for e in request.data['analyzers']
               if e['descriptor']['analyzer_id'] == pair['analyzer_id']
               and e['descriptor_sha256'] == pair['descriptor_sha256']]
    subjects = [s for s in request.data['subjects'] if s['subject_key'] == pair['subject_key']]
    require(len(entries) == len(subjects) == 1, 'analyzer_work_foreign_unit', exit_code=6)
    return entries[0], subjects[0]


def unit_value(request, pair, engine, subject, findings):
    return dict(binding=request.binding, pair=pair, engine_sha256=digest(engine),
                subject=subject, findings=findings)


def check_unit(request, pair, rows, value):
    entry, original = select(request, pair)
    engine = next(e for e in rows if e['analyzer_id'] == entry['descriptor']['analyzer_id'])
    shape(value, ('binding', 'pair', 'engine_sha256', 'subject', 'findings'))
    require(value['binding'] == request.binding and value['pair'] == pair
        and value['engine_sha256'] == digest(engine), 'analyzer_work_unit_binding', exit_code=6)
    findings = check_findings(value['findings'], {original['subject_key']})
    report_subjects([value['subject']], {'subjects':[original]}, findings)
    require(set(findings) == set(value['subject'].get('findings', [])),
            'analyzer_work_unreferenced_finding', exit_code=5)
    check_language_unit(request, entry, engine, original, value)
    return value


def package_from_units(request, rows, units, *, document=None):
    check_engines(request, rows)
    run_ids = {} if document is None else {
        r.data['analyzer']['descriptor']['analyzer_id']:r.data['run_id']
        for r in ReportPackage(encoded(document), request=request).reports}
    reports = []
    for entry, engine in zip(request.data['analyzers'], rows):
        subjects, findings = [], []
        for original in request.data['subjects']:
            pair = dict(analyzer_id=entry['descriptor']['analyzer_id'],
                descriptor_sha256=entry['descriptor_sha256'], subject_key=original['subject_key'])
            key = 'subject:' + entry['descriptor_sha256'] + ':' + original['subject_key']
            unit = check_unit(request, pair, rows, units[key])
            subjects.append(unit['subject']); findings.extend(unit['findings'])
        subjects.sort(key=lambda s:s['subject_key'])
        findings.sort(key=lambda f:f['finding_id'])
        coverage = exact_coverage(subjects)
        status = ('failed' if coverage['failed'] else 'unavailable'
            if coverage['open'] == coverage['expected'] else 'partial'
            if coverage['open'] else 'complete')
        reports.append(create_report(request, analyzer_id=engine['analyzer_id'],
            engine=engine['engine'], subjects=subjects, findings=findings, run_status=status,
            run_id=run_ids.get(engine['analyzer_id']),
            operational={'execution_supported':engine['reason'] is None, 'reason':engine['reason']},
            extensions={'specroad.engine_inventory':engine['inventory']}))
    return create_package(request, reports)
