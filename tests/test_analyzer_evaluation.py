"""Currentness compares real native files and independently supplied inputs."""
from copy import deepcopy
import json

import pytest

from specroad.analyzers.descriptors import AnalyzerDescriptor
from specroad.analyzers.evaluation import evaluate_reports
from specroad.analyzers.packages import create_package
from specroad.analyzers.requests import analyzer_binding, create_request
from specroad.analyzers.reports import create_report, subject_result
from specroad.analyzers.subjects import request_from_project
from specroad.model.paths import artifact_path
from support.read_only import inventory, no_write_attempts
from test_analyzer_descriptors import external
from test_analyzer_reports import unknown_engine, finding
from test_analyzer_requests import checksum
from test_analyzer_subjects import project


def current_inputs():
    descriptors = []
    for name in ('example.reviewer','example.second'):
        value = external(); value['analyzer_id'] = name
        descriptors.append(analyzer_binding(AnalyzerDescriptor(json.dumps(value).encode()), ['quality']))
    context = {'instruction':'A passive full JSON resource; never a command.', 'text':'原文'}
    return dict(analyzers=descriptors, settings={name:{} for name in ('example.reviewer','example.second')},
        context=[dict(resource_id='explicit-resource', value=context, sha256=checksum(context))],
        extensions={'example.future':{'flag':False}})


def observations(request, *, differing=True):
    reports = []
    for index, entry in enumerate(request.data['analyzers']):
        subjects = [subject_result(s, status='done', payload={'example.quality':{'label':index if differing else 0}})
                    for s in request.data['subjects']]
        item = finding([s['subject_key'] for s in subjects]); item['finding_id'] = f'local-{index}'
        reports.append(create_report(request, analyzer_id=entry['descriptor']['analyzer_id'],
            engine=unknown_engine(), subjects=sorted(subjects, key=lambda s:s['subject_key']),
            run_status='complete', findings=[item], run_id='AR-'+str(index)*26))
    return reports


def prepared(root, *, differing=True):
    values = project(root); supplied = current_inputs()
    request = request_from_project(root, **supplied, analysis_id='evaluation-test')
    package = create_package(request, observations(request, differing=differing))
    return values, supplied, request, package


def test_current_means_original_inputs_match_not_a_quality_or_evidence_pass(tmp_path):
    _, supplied, request, package = prepared(tmp_path)
    before = inventory(tmp_path)
    raw = json.dumps(package.data, indent=3, ensure_ascii=False).encode()
    with no_write_attempts(): result = evaluate_reports([raw], project=tmp_path, current_inputs=supplied)
    assert inventory(tmp_path) == before and result.originals == (raw,)
    assert result.data['all_reports_current']
    assert [r['currentness'] for r in result.data['reports']] == ['current','current']
    assert all(r['request_binding_verified'] for r in result.data['reports'])
    assert [r['report'] for r in result.data['reports']] == package.data['reports']
    assert len(result.data['disagreements']) == len(request.data['subjects'])
    assert not {'gate_passed','all_languages_confirmed','verification_result','evidence'} & result.data.keys()


@pytest.mark.parametrize('field,value', [('statement','Changed full text.'),('title','Changed unrelated title.'),
    ('revision',2),('language','en'),('normative_force','may')])
def test_any_original_binding_change_is_stale_without_rewriting_report(tmp_path, field, value):
    values, supplied, request, package = prepared(tmp_path)
    values[0][field] = value
    (tmp_path/artifact_path('requirement',values[0]['id'],'SR')).write_text(json.dumps(values[0]))
    before = inventory(tmp_path)
    with no_write_attempts(): result = evaluate_reports([package.original_bytes], project=tmp_path, current_inputs=supplied)
    assert [r['currentness'] for r in result.data['reports']] == ['stale','stale']
    assert all(r['changed_subject_keys'] == [request.data['subjects'][0]['subject_key']] for r in result.data['reports'])
    assert not result.data['all_reports_current'] and inventory(tmp_path) == before
    assert [r['report'] for r in result.data['reports']] == package.data['reports']


@pytest.mark.parametrize('field', ['context','settings','extensions','analyzers'])
def test_independently_supplied_current_resources_are_not_replaced_by_old_request(tmp_path, field):
    _, supplied, _, package = prepared(tmp_path)
    if field == 'context':
        supplied['context'][0]['value']['text'] = 'Changed explicitly supplied context'
        supplied['context'][0]['sha256'] = checksum(supplied['context'][0]['value'])
    elif field == 'settings': supplied[field]['example.reviewer']['threshold'] = '0.99'
    elif field == 'extensions': supplied[field]['example.future']['flag'] = 0
    else:
        descriptor = supplied[field][0]['descriptor']; descriptor['adapter_version'] = '2.3.2'
        supplied[field][0] = analyzer_binding(AnalyzerDescriptor(json.dumps(descriptor).encode()), ['quality'])
    result = evaluate_reports([package.original_bytes], project=tmp_path, current_inputs=supplied)
    assert all(r['currentness'] == 'stale' and r['changed_inputs'] == [field] for r in result.data['reports'])


@pytest.mark.parametrize('missing', ['project','current_inputs','request'])
def test_missing_authority_is_unavailable_never_implicitly_current(tmp_path, missing):
    _, supplied, _, package = prepared(tmp_path)
    kwargs = dict(project=tmp_path, current_inputs=supplied)
    inputs = [package.original_bytes]
    if missing == 'request': inputs = [package.reports[0].canonical_bytes]
    else: del kwargs[missing]
    with no_write_attempts(): result = evaluate_reports(inputs, **kwargs)
    assert all(r['currentness'] == 'unavailable' for r in result.data['reports'])
    assert not result.data['all_reports_current']
    if missing == 'request': assert not result.data['reports'][0]['request_binding_verified']


@pytest.mark.parametrize('bound', [False, True])
def test_integrity_failure_is_invalid_even_when_working_state_is_absent(tmp_path, bound):
    _, _, request, package = prepared(tmp_path)
    value = package.reports[0].data; value['result_sha256'] = 'f'*64
    raw = json.dumps(value).encode()
    with no_write_attempts(): result = evaluate_reports([raw], request=request if bound else None)
    assert result.data['reports'][0]['currentness'] == 'invalid'
    assert result.data['reports'][0]['reason'] == 'analyzer_result_hash_mismatch'
    assert result.originals == (raw,) and not result.data['all_reports_current']


def test_all_selected_inputs_remain_visible_including_invalid_and_duplicate_files(tmp_path):
    _, supplied, request, package = prepared(tmp_path)
    first = package.reports[0].canonical_bytes
    result = evaluate_reports([first,b'{',package.original_bytes,first], request=request,
                              project=tmp_path,current_inputs=supplied)
    rows = result.data['reports']
    assert [r['input_index'] for r in rows] == [0,1,2,2,3]
    assert [r['currentness'] for r in rows] == ['current','invalid','current','current','current']
    assert rows[0]['report'] == rows[4]['report'] and not result.data['all_reports_current']


def test_same_observations_with_distinct_provenance_are_not_majority_voted(tmp_path):
    _, supplied, _, package = prepared(tmp_path, differing=False)
    result = evaluate_reports([package.original_bytes], project=tmp_path, current_inputs=supplied)
    assert result.data['disagreements'] == []
    assert len(result.data['reports']) == 2
    assert result.data['reports'][0]['report']['analyzer'] != result.data['reports'][1]['report']['analyzer']
    assert [r['report']['findings'][0]['finding_id'] for r in result.data['reports']] == ['local-0','local-1']


def test_evaluation_owns_outputs_and_retains_every_disagreement_variant(tmp_path):
    _, supplied, _, package = prepared(tmp_path)
    result = evaluate_reports([package.original_bytes], project=tmp_path, current_inputs=supplied)
    original = result.canonical_bytes
    value = result.data
    for disagreement in value['disagreements']:
        assert disagreement['code'] == 'analyzer_disagreement'
        assert disagreement['comparison'] == 'structural_subject_observation'
        assert len(disagreement['variants']) == 2
        assert len({v['observation_sha256'] for v in disagreement['variants']}) == 2
        assert all('engine' in v and 'analyzer' in v for v in disagreement['variants'])
    value.clear(); supplied.clear()
    assert result.canonical_bytes == original


def test_individually_selected_pointers_are_not_expanded_to_cross_product(tmp_path):
    project(tmp_path); supplied = current_inputs()
    full = request_from_project(tmp_path, **supplied, field_pointers=('/statement','/title'), analysis_id='ragged')
    data = full.data; data['subjects'] = [data['subjects'][0],data['subjects'][-1]]
    data['context']['subject_keys'] = sorted(s['subject_key'] for s in data['subjects'])
    request = create_request(**{k:v for k,v in data.items() if k not in ('contract_version','request_id','snapshot_sha256')}, analysis_id='ragged')
    package = create_package(request, observations(request))
    result = evaluate_reports([package.original_bytes], project=tmp_path,current_inputs=deepcopy(supplied))
    assert result.data['all_reports_current']
