"""Exact coverage and independent observation hashes; no engine is fabricated."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from specroad.analyzers.requests import create_request
from specroad.analyzers.reports import AnalyzerReport, create_report, subject_result
from specroad.model.identity_tokens import decode128
from support.read_only import no_write_attempts
from test_analyzer_requests import checksum, inputs


def request_value():
    data = inputs()
    first = data['subjects'][0]
    data['subjects'] = []
    for i in range(4):
        subject = deepcopy(first)
        subject['artifact_id'] = f'TEST-REQ-{i+1:04d}'
        subject['subject_key'] = checksum({k:subject[k] for k in (
            'artifact_id','artifact_revision','artifact_sha256','field_pointer')})
        data['subjects'].append(subject)
    data['context']['subject_keys'] = sorted(s['subject_key'] for s in data['subjects'])
    return create_request(**data,analysis_id='report-input')


def unknown_engine():
    # Explicitly unknown external-engine facts, not an actual measured runtime.
    return {'adapter_version':'2.3.1', **{key:{'value':None,'reason':'Not supplied by this synthetic external source.'}
        for key in ('library_versions','model_sha256','candidates','candidates_sha256',
                    'preprocessing_version','unicode_version','runtime_fingerprint','numpy_fingerprint')}}


def report_options(request, states=('done','undetermined','failed','open'), status='partial'):
    values = [subject_result(subject,status=state,payload={'example.observation':{'label':state}})
              for subject,state in zip(request.data['subjects'],states)]
    return dict(analyzer_id='example.reviewer',engine=unknown_engine(),
        subjects=sorted(values,key=lambda s:s['subject_key']),run_status=status)


def report_hash(value):
    return checksum({key:value[key] for key in ('contract_version','report_version','snapshot_sha256',
        'analyzer','engine','subjects','coverage','run_status','findings','extensions')})


def encode_report(value):
    value['result_sha256'] = report_hash(value)
    return json.dumps(value,ensure_ascii=False).encode()


def finding(keys):
    return dict(finding_id='external finding 1',code='future.vendor.rule',severity='warning',
        subject_keys=sorted(keys),message='Independent observation',rationale='Synthetic test rationale',
        details={'future.vendor.measure':{'kind':'score','value':'-0.125000000000',
            'score_semantics':'uncalibrated-log-score'},
            'future.vendor.data':{'kind':'json','value':{'nested':[1,'opaque']}}},
        suggestion={'command':'rm -rf /untrusted-example','instructions':'Not executable'})


def test_four_outcomes_cover_every_original_once_and_hash_exact_projection():
    request = request_value()
    report = create_report(request,**report_options(request))
    keys = [s['subject_key'] for s in request.data['subjects']]
    assert report.data['coverage'] == {'expected':sorted(keys), 'done':[keys[0]],
        'undetermined':[keys[1]],'failed':[keys[2]],'open':[keys[3]],
        'counts':{'expected':4,'done':1,'undetermined':1,'failed':1,'open':1}}
    assert report.result_sha256 == report_hash(report.data)
    assert len(decode128(report.data['run_id'][3:])) == 16
    originals = {s['subject_key']:s for s in request.data['subjects']}
    for subject in report.data['subjects']:
        assert {k:v for k,v in subject.items() if k not in ('status','payload')} == {
            k:v for k,v in originals[subject['subject_key']].items() if k != 'value'}


@pytest.mark.parametrize('states,status', [
    (('done',)*4,'complete'), (('undetermined',)*4,'complete'),
    (('failed',)*4,'failed'), (('open',)*4,'partial'), (('open',)*4,'unavailable'),
    (('done','undetermined','failed','open'),'failed')])
def test_complete_means_processed_not_positive_quality(states,status):
    request = request_value()
    result = create_report(request,**report_options(request,states,status)).data
    assert result['run_status'] == status
    assert sum(result['coverage']['counts'][k] for k in ('done','undetermined','failed','open')) == 4
    assert 'verification_result' not in result


def test_findings_and_unknown_namespaces_remain_passive_owned_data():
    request = request_value(); kwargs = report_options(request)
    item = finding([kwargs['subjects'][0]['subject_key']])
    kwargs['subjects'][0]['findings'] = [item['finding_id']]
    kwargs['findings'] = [item]
    kwargs['extensions'] = {'future.vendor':{'retained':['all',{'values':True}]}}
    with no_write_attempts():
        result = create_report(request,**kwargs)
        reread = AnalyzerReport(result.canonical_bytes,request)
    assert reread.data['findings'] == [item]
    assert reread.data['extensions'] == kwargs['extensions']
    item['suggestion']['command'] = 'changed'
    assert result.data['findings'][0]['suggestion']['command'] == 'rm -rf /untrusted-example'
    assert result.provenance['analyzer'] == request.data['analyzers'][0]


def test_transport_hash_binds_original_bytes_independently_of_observation():
    request = request_value(); report = create_report(request,**report_options(request))
    pretty = json.dumps(report.data,indent=3,ensure_ascii=False).encode()
    read = AnalyzerReport(pretty,request)
    assert read.full_file_sha256 == sha256(pretty).hexdigest()
    assert read.full_file_sha256 != report.full_file_sha256
    assert read.result_sha256 == report.result_sha256
    assert read.canonical_bytes == report.canonical_bytes


def test_distinct_run_identity_time_and_pid_leave_observation_identical():
    request = request_value(); kwargs = report_options(request)
    first = create_report(request,**kwargs,run_id='AR-'+'0'*26,operational={'pid':17,'elapsed':1,'captured':'first'})
    second = create_report(request,**kwargs,run_id='AR-'+'1'*26,operational={'pid':99,'elapsed':999,'captured':'second'})
    assert first.observation == second.observation
    assert first.result_sha256 == second.result_sha256
    assert first.full_file_sha256 != second.full_file_sha256
    assert first.operational['pid'] == 17 and second.operational['pid'] == 99


def test_original_request_and_all_returned_projections_are_owned():
    request = request_value(); report = create_report(request,**report_options(request))
    original = report.canonical_bytes
    for value in (report.data,report.observation,report.provenance,report.operational):
        value.clear()
    assert report.canonical_bytes == original
