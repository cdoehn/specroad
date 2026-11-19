"""Projectless complete packages with independent request and transport oracles."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from specroad.analyzers._values import AnalyzerError
from specroad.analyzers.descriptors import AnalyzerDescriptor
from specroad.analyzers.packages import ReportPackage, create_package, verify_worker_result
from specroad.analyzers.requests import AnalyzerRequest, analyzer_binding, create_request
from specroad.analyzers.reports import create_report
from support.read_only import no_write_attempts
from test_analyzer_reports import request_value, report_options, finding


def package_values():
    data = request_value().data
    second = deepcopy(data['analyzers'][0]['descriptor'])
    second['analyzer_id'] = 'example.second'
    data['analyzers'].append(analyzer_binding(AnalyzerDescriptor(json.dumps(second).encode()), ['quality']))
    data['settings']['example.second'] = {}
    request = create_request(**{k:v for k,v in data.items() if k not in ('contract_version','request_id','snapshot_sha256')},
                             analysis_id=data['request_id'])
    reports = []
    for index, analyzer in enumerate(request.data['analyzers']):
        options = report_options(request)
        options['analyzer_id'] = analyzer['descriptor']['analyzer_id']
        options['findings'] = [finding([options['subjects'][0]['subject_key']])]
        reports.append(create_report(request, **options, run_id='AR-'+str(index)*26))
    return request, reports


def test_complete_multi_analyzer_package_is_owned_and_projectless():
    request, reports = package_values()
    with no_write_attempts():
        package = create_package(request, reports)
        reread = ReportPackage(package.canonical_bytes)
    assert reread.request.canonical_bytes == request.canonical_bytes
    assert [r.data for r in reread.reports] == [r.data for r in reports]
    assert len(reread.reports) == 2
    copy = reread.data; copy['reports'].clear(); copy['request'].clear()
    assert reread.canonical_bytes == package.canonical_bytes
    assert all(r.data['coverage']['counts']['failed'] == 1 for r in reread.reports)


def test_multiple_runs_of_same_analyzer_keep_order_findings_and_provenance():
    request, reports = package_values()
    options = report_options(request)
    options['engine']['runtime_fingerprint'] = {'value':'a'*64, 'reason':None}
    extra = create_report(request, **options, run_id='AR-'+'2'*26)
    package = create_package(request, [extra, *reports])
    assert [r.data['run_id'] for r in package.reports] == [extra.data['run_id'], *[r.data['run_id'] for r in reports]]
    assert package.reports[0].provenance != package.reports[1].provenance
    assert package.reports[1].data['findings'] == reports[0].data['findings']


def test_original_package_bytes_are_distinct_from_embedded_canonical_values():
    request, reports = package_values()
    raw = json.dumps(create_package(request, reports).data, ensure_ascii=False, indent=4).encode()
    package = ReportPackage(raw)
    assert package.original_bytes == raw
    assert package.full_file_sha256 == sha256(raw).hexdigest()
    assert package.canonical_bytes != raw
    assert [r.result_sha256 for r in package.reports] == [r.result_sha256 for r in reports]


@pytest.mark.parametrize('coordinate', ['id','snapshot'])
def test_both_request_coordinates_are_mandatory(coordinate):
    request, reports = package_values()
    other = request.data
    if coordinate == 'id':
        other['request_id'] = 'different-analysis'
        rebound = AnalyzerRequest(json.dumps(other).encode())
        assert rebound.binding['snapshot_sha256'] == request.binding['snapshot_sha256']
    else:
        other['settings']['example.reviewer']['changed'] = True
        rebound = create_request(**{k:v for k,v in other.items() if k not in ('contract_version','request_id','snapshot_sha256')},
                                 analysis_id=other['request_id'])
        assert rebound.binding['request_id'] == request.binding['request_id']
    with no_write_attempts(), pytest.raises(AnalyzerError):
        create_package(rebound, reports)


@pytest.mark.parametrize('coordinate', ['analyzer','engine'])
def test_worker_result_uses_same_binding_and_expected_provenance(coordinate):
    request, reports = package_values()
    report = reports[0]
    with no_write_attempts():
        validated = verify_worker_result(report.canonical_bytes, request, **report.provenance)
    assert validated.canonical_bytes == report.canonical_bytes
    expected = report.provenance
    expected[coordinate]['extra'] = 'not the expected worker'
    with pytest.raises(AnalyzerError) as error:
        verify_worker_result(report.canonical_bytes, request, **expected)
    assert error.value.exit_code == 6
