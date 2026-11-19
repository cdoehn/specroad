"""Malformed observations, independent provenance and exact transport bindings."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from specroad.analyzers._values import AnalyzerError
from specroad.analyzers.reports import AnalyzerReport, create_report
from specroad.analyzers.requests import AnalyzerRequest
from support.read_only import no_write_attempts
from test_analyzer_reports import (checksum, encode_report, finding, report_options,
                                  request_value)


def changed(value, fault):
    if fault == 'duplicate': value['subjects'][1] = deepcopy(value['subjects'][0])
    elif fault == 'missing': value['subjects'].pop()
    elif fault == 'foreign': value['subjects'][0]['subject_key'] = 'f'*64
    elif fault == 'revision': value['subjects'][0]['artifact_revision'] += 1
    elif fault == 'bool_revision': value['subjects'][0]['artifact_revision'] = True
    elif fault == 'hash': value['subjects'][0]['artifact_sha256'] = 'f'*64
    elif fault == 'value_hash': value['subjects'][0]['value_sha256'] = 'f'*64
    elif fault == 'pointer': value['subjects'][0]['field_pointer'] = '/title'
    elif fault == 'language': value['subjects'][0]['declared_language'] = 'en'
    elif fault == 'force': value['subjects'][0]['normative_force'] = 'may'
    elif fault == 'value': value['subjects'][0]['value'] = 'Do not smuggle duplicated input'
    elif fault == 'order': value['subjects'].reverse()
    elif fault == 'counts': value['coverage']['counts']['expected'] += 1
    elif fault == 'bool_counts': value['coverage']['counts']['done'] = True
    elif fault == 'sets': value['coverage']['done'] = value['coverage']['expected']
    elif fault == 'complete': value['run_status'] = 'complete'
    elif fault == 'unavailable': value['run_status'] = 'unavailable'
    elif fault == 'request_id': value['request_id'] += '-other'
    elif fault == 'snapshot': value['snapshot_sha256'] = 'f'*64
    elif fault == 'descriptor': value['analyzer']['descriptor']['adapter_version'] = '99.0.0'
    elif fault == 'payload_namespace': value['subjects'][0]['payload'] = {'invalid':1}
    elif fault == 'extension_namespace': value['extensions'] = {'invalid':1}
    elif fault == 'run_id': value['run_id'] = 'AR-'+'Z'*26
    elif fault == 'operational': value['operational'] = []
    elif fault == 'unknown': value['unrecognized'] = True
    elif fault == 'version': value['report_version'] = '2.0.0'
    elif fault == 'subject_object': value['subjects'][0] = []
    elif fault == 'subject_key_type': value['subjects'][0]['subject_key'] = []
    else: raise AssertionError(fault)


@pytest.mark.parametrize('fault', ['duplicate','missing','foreign','revision','bool_revision','hash','value_hash',
    'pointer','language','force','value','order','counts','bool_counts','sets','complete','unavailable',
    'request_id','snapshot','descriptor','payload_namespace','extension_namespace','run_id','operational',
    'unknown','version','subject_object','subject_key_type'])
def test_rehashed_invalid_envelopes_are_not_accepted(fault):
    request = request_value(); value = create_report(request,**report_options(request)).data
    changed(value,fault)
    with no_write_attempts(), pytest.raises(AnalyzerError) as failure:
        AnalyzerReport(encode_report(value),request)
    assert failure.value.exit_code == 3


@pytest.mark.parametrize('fault', ['duplicate','foreign','code','severity','detail','score','semantics','reference','reference_subject'])
def test_findings_are_scoped_unique_and_typed(fault):
    request = request_value(); value = create_report(request,**report_options(request)).data
    key = value['subjects'][0]['subject_key']; item = finding([key]); value['findings'] = [item]
    if fault == 'duplicate': value['findings'].append(deepcopy(item))
    elif fault == 'foreign': item['subject_keys'] = ['f'*64]
    elif fault == 'code': item['code'] = 'unqualified'
    elif fault == 'severity': item['severity'] = 'passed'
    elif fault == 'detail': item['details']['future.confidence'] = 0.99
    elif fault == 'score': item['details']['future.vendor.measure']['value'] = 'NaN'
    elif fault == 'semantics': del item['details']['future.vendor.measure']['score_semantics']
    elif fault == 'reference': value['subjects'][0]['findings'] = ['missing finding']
    else: value['subjects'][1]['findings'] = [item['finding_id']]
    with pytest.raises(AnalyzerError): AnalyzerReport(encode_report(value),request)


@pytest.mark.parametrize('fault', ['missing_reason','known_reason','model_hash','candidates','candidate_hash','runtime','adapter','unknown'])
def test_engine_unknown_facts_require_reasons_and_known_facts_remain_bound(fault):
    request = request_value(); value = create_report(request,**report_options(request)).data
    engine = value['engine']
    if fault == 'missing_reason': engine['model_sha256']['reason'] = None
    elif fault == 'known_reason': engine['model_sha256'] = {'value':'a'*64,'reason':'Not known after all'}
    elif fault == 'model_hash': engine['model_sha256'] = {'value':'bad','reason':None}
    elif fault == 'candidates': engine['candidates'] = {'value':['en','en'],'reason':None}
    elif fault == 'candidate_hash':
        engine['candidates'] = {'value':['en','de'],'reason':None}
        engine['candidates_sha256'] = {'value':checksum(['de','en']),'reason':None}
    elif fault == 'runtime': engine['runtime_fingerprint'] = {'value':{},'reason':None}
    elif fault == 'adapter': engine['adapter_version'] = '9.0.0'
    else: engine['host_path'] = '/not-a-semantic-input'
    with pytest.raises(AnalyzerError): AnalyzerReport(encode_report(value),request)


def test_declared_known_fingerprints_and_candidate_order_change_the_result():
    request = request_value(); kwargs = report_options(request)
    for key in ('model_sha256','runtime_fingerprint','numpy_fingerprint'):
        kwargs['engine'][key] = {'value':checksum({'synthetic':key}),'reason':None}
    kwargs['engine']['library_versions'] = {'value':{'example-library':'1.2-test'},'reason':None}
    kwargs['engine']['candidates'] = {'value':['en','de'],'reason':None}
    kwargs['engine']['candidates_sha256'] = {'value':checksum(['en','de']),'reason':None}
    kwargs['engine']['preprocessing_version'] = {'value':'test-v1','reason':None}
    kwargs['engine']['unicode_version'] = {'value':'test-unicode','reason':None}
    first = create_report(request,**kwargs)
    kwargs['engine']['candidates']['value'].reverse()
    kwargs['engine']['candidates_sha256']['value'] = checksum(['de','en'])
    second = create_report(request,**kwargs)
    assert first.result_sha256 != second.result_sha256
    assert first.provenance != second.provenance


@pytest.mark.parametrize('coordinate', ['analyzer','engine','file'])
def test_provenance_and_original_transport_binding_checked_independently(coordinate):
    request = request_value(); report = create_report(request,**report_options(request))
    expected = report.provenance
    report.require_provenance(**expected)
    report.require_transport_hash(report.full_file_sha256)
    if coordinate == 'file':
        pretty = json.dumps(report.data,indent=4).encode()
        with pytest.raises(AnalyzerError) as failure:
            report.require_transport_hash(sha256(pretty).hexdigest())
    else:
        expected[coordinate]['extensions' if coordinate=='analyzer' else 'extra'] = {}
        with pytest.raises(AnalyzerError) as failure:
            report.require_provenance(**expected)
    assert failure.value.exit_code == 6


def test_analysis_identity_is_separate_even_when_snapshot_matches():
    request = request_value(); report = create_report(request,**report_options(request))
    other = request.data; other['request_id'] = 'another-analysis'
    rebound = AnalyzerRequest(json.dumps(other).encode())
    assert rebound.binding['snapshot_sha256'] == request.binding['snapshot_sha256']
    with pytest.raises(AnalyzerError): AnalyzerReport(report.canonical_bytes,rebound)
    value = report.data; value['request_id'] = 'another-analysis'
    reread = AnalyzerReport(encode_report(value),rebound)
    assert reread.result_sha256 == report.result_sha256


@pytest.mark.parametrize('raw', [b'{', b'[]', b'{"duplicate":1,"duplicate":2}', b'{"x":NaN}', b'\xff', 'text'])
def test_invalid_transport_bytes_do_not_escape_as_python_errors(raw):
    with pytest.raises(AnalyzerError): AnalyzerReport(raw,request_value())


def test_unknown_namespaced_payloads_never_acquire_execution_or_approval():
    request = request_value(); kwargs = report_options(request)
    kwargs['subjects'][0]['payload']['unknown.vendor'] = {'code':'import socket; open credentials', 'passed':True}
    with no_write_attempts():
        report = create_report(request,**kwargs)
        report.require_provenance(**report.provenance)
    assert report.data['subjects'][0]['payload']['unknown.vendor']['passed'] is True
    assert 'verification_result' not in report.observation
    assert 'approval' not in report.observation


@pytest.mark.parametrize('findings', [None, 'command', {'not':'a finding array'}])
def test_report_constructor_rejects_invalid_finding_options(findings):
    request = request_value()
    with pytest.raises(AnalyzerError) as failure:
        create_report(request,**report_options(request),findings=findings)
    assert failure.value.exit_code == 2


@pytest.mark.parametrize('route', ['reader', 'expected_provenance'])
def test_descriptor_boolean_cannot_be_replaced_by_equal_python_number(route):
    request = request_value(); report = create_report(request,**report_options(request))
    analyzer = report.provenance['analyzer']
    assert analyzer['descriptor']['extensions']['example.future']['enabled'] is False
    analyzer['descriptor']['extensions']['example.future']['enabled'] = 0
    if route == 'reader':
        value = report.data; value['analyzer'] = analyzer
        with pytest.raises(AnalyzerError) as failure:
            AnalyzerReport(encode_report(value),request)
        assert failure.value.exit_code == 3
    else:
        with pytest.raises(AnalyzerError) as failure:
            report.require_provenance(analyzer=analyzer,engine=report.provenance['engine'])
        assert failure.value.exit_code == 6
