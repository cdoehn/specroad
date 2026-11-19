"""No partial import, foreign bindings or unbound integrity bypasses."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from specroad.analyzers._values import AnalyzerError
from specroad.analyzers.packages import ReportPackage, create_package, read_unbound_report, verify_worker_result
from specroad.analyzers.requests import AnalyzerRequest
from support.read_only import no_write_attempts
from test_analyzer_packages import package_values
from test_analyzer_reports import encode_report, report_hash
from test_analyzer_reports_right import changed


@pytest.mark.parametrize('fault', ['duplicate','missing','foreign','revision','bool_revision','hash','value_hash',
    'pointer','language','force','value','order','counts','bool_counts','sets','complete','unavailable',
    'request_id','snapshot','descriptor','payload_namespace','extension_namespace','run_id','operational',
    'unknown','version','subject_object','subject_key_type'])
def test_one_rehashed_bad_report_blocks_the_entire_package(fault):
    request, reports = package_values()
    value = create_package(request, reports).data
    changed(value['reports'][1], fault)
    value['reports'][1]['result_sha256'] = report_hash(value['reports'][1])
    with no_write_attempts(), pytest.raises(AnalyzerError) as error:
        ReportPackage(json.dumps(value).encode())
    assert error.value.exit_code == 3


@pytest.mark.parametrize('fault', ['version','unknown','array','empty','missing_analyzer','duplicate_run',
    'request_hash','result_hash','request_field','bool_descriptor'])
def test_package_structure_coverage_and_hashes_fail_closed(fault):
    request, reports = package_values(); value = create_package(request, reports).data
    if fault == 'version': value['package_version'] = '2.0.0'
    elif fault == 'unknown': value['authorization'] = True
    elif fault == 'array': value['reports'] = {}
    elif fault == 'empty': value['reports'] = []
    elif fault == 'missing_analyzer': value['reports'].pop()
    elif fault == 'duplicate_run': value['reports'][1]['run_id'] = value['reports'][0]['run_id']
    elif fault == 'request_hash': value['request']['snapshot_sha256'] = 'f'*64
    elif fault == 'result_hash': value['reports'][1]['result_sha256'] = 'f'*64
    elif fault == 'request_field': value['request']['host'] = 'unbound'
    else:
        value['reports'][1]['analyzer']['descriptor']['extensions']['example.future']['enabled'] = 0
        value['reports'][1]['result_sha256'] = report_hash(value['reports'][1])
    with pytest.raises(AnalyzerError): ReportPackage(json.dumps(value).encode())


@pytest.mark.parametrize('raw', [b'{',b'[]',b'\xff',b'{"package_version":1,"package_version":2}',b'{"x":NaN}','path.json'])
def test_malformed_transport_never_becomes_a_path_or_python_exception(raw):
    with no_write_attempts(), pytest.raises(AnalyzerError): ReportPackage(raw)


def test_explicit_request_and_outer_transport_are_checked_independently():
    request, reports = package_values()
    package = create_package(request, reports)
    ReportPackage(package.original_bytes, request=request).require_transport_hash(sha256(package.original_bytes).hexdigest())
    data = request.data; data['request_id'] += '-other'
    with pytest.raises(AnalyzerError): ReportPackage(package.original_bytes, request=AnalyzerRequest(json.dumps(data).encode()))
    pretty = json.dumps(package.data, indent=2).encode()
    with pytest.raises(AnalyzerError) as error: package.require_transport_hash(sha256(pretty).hexdigest())
    assert error.value.exit_code == 6


def test_unbound_reader_preserves_observation_but_never_supplies_a_request():
    _, reports = package_values()
    raw = json.dumps(reports[0].data, indent=2).encode()
    with no_write_attempts(): result = read_unbound_report(raw)
    assert result == reports[0].data
    assert 'request' not in result and 'currentness' not in result


@pytest.mark.parametrize('fault', ['duplicate','bool_revision','pointer','value','order','counts','bool_counts',
    'sets','complete','unavailable','descriptor','payload_namespace','extension_namespace','run_id',
    'operational','unknown','version','subject_object','subject_key_type'])
def test_unbound_integrity_is_checked_even_without_request(fault):
    _, reports = package_values(); value = reports[0].data
    changed(value, fault)
    with pytest.raises(AnalyzerError): read_unbound_report(encode_report(value))


def test_missing_request_does_not_let_worker_validate_only_self_declared_hashes():
    request, reports = package_values(); value = deepcopy(reports[0].data)
    value['subjects'].pop(); value['result_sha256'] = report_hash(value)
    with pytest.raises(AnalyzerError): verify_worker_result(json.dumps(value).encode(), request, **reports[0].provenance)
