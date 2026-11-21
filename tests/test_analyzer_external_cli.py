"""Foreign descriptors are usable file contracts without execution authority."""
import json

import pytest

from specroad.analyzers.requests import AnalyzerRequest, analyzer_binding
from specroad.analyzers.descriptors import AnalyzerDescriptor
from specroad.analyzers.registry import builtin_descriptor
from specroad.analyzers.packages import ReportPackage, create_package
from specroad.cli.results import thaw
from support.read_only import inventory, no_write_attempts
from test_analyzer_subjects import project
from test_analyzer_evaluation import current_inputs, observations
from test_analyzer_cli import call, json_file, observation_files, BUILTIN


def foreign_request(root):
    values=project(root); inputs=current_inputs()
    json_file(root/'inputs.json',inputs)
    result=call(['request','--project',str(root),'--inputs','inputs.json',
        '--analyzer','example.second','--analyzer','example.reviewer','--analysis-id','foreign-roundtrip'],root)
    assert result.exit_code==0
    return values,inputs,AnalyzerRequest(json.dumps(thaw(result.result)).encode())


def test_external_multianalyzer_request_is_complete_and_exactly_bound(tmp_path):
    values,inputs,request=foreign_request(tmp_path)
    data=request.data
    assert data['analyzers']==inputs['analyzers'] and data['settings']==inputs['settings']
    assert [s['value'] for s in data['subjects']]==[v['statement'] for v in values]
    assert data['context']['resources']==inputs['context']
    assert data['request_id']=='foreign-roundtrip'


@pytest.mark.parametrize('name',['list','describe'])
def test_foreign_descriptors_can_be_inspected_without_project_initialization(tmp_path,name):
    inputs=current_inputs();json_file(tmp_path/'inputs.json',inputs);before=inventory(tmp_path)
    args=[name,*(['example.reviewer'] if name=='describe' else []),'--inputs','inputs.json']
    with no_write_attempts():result=call(args,tmp_path)
    assert result.exit_code==0
    rows=thaw(result.result)['analyzers']
    assert [r['descriptor']['analyzer_id'] for r in rows]==(['example.reviewer'] if name=='describe'
        else ['example.reviewer','example.second',BUILTIN])
    for row in rows:
        known = row['descriptor'] == builtin_descriptor().data
        assert row['availability']['execution_supported'] is known
        assert row['availability']['availability'] == ('not_checked' if known else 'external_result_only')
    assert inventory(tmp_path)==before


def test_real_foreign_file_roundtrip_uses_existing_validator_without_running_worker(tmp_path):
    _,inputs,request=foreign_request(tmp_path)
    package=create_package(request,observations(request))
    original=json_file(tmp_path/'answer.json',package.data);json_file(tmp_path/'request.json',request.data)
    before=inventory(tmp_path)
    common=['--project',str(tmp_path),'--inputs','inputs.json','--request','request.json']
    with no_write_attempts():
        imported=call(['import','answer.json',*common],tmp_path)
        shown=call(['show','answer.json',*common],tmp_path)
        evaluated=call(['evaluate','answer.json',*common],tmp_path)
    assert imported.exit_code==shown.exit_code==evaluated.exit_code==0
    assert all(r['currentness']=='current' for r in evaluated.result['evaluation']['reports'])
    assert thaw(imported.result)['sources'][0]['document']==package.data
    assert (tmp_path/'answer.json').read_bytes()==original and inventory(tmp_path)==before


@pytest.mark.parametrize('mode',['selected','data_only'])
def test_foreign_run_preserves_every_requested_analyzer_as_unavailable(tmp_path,mode):
    _,_,request=foreign_request(tmp_path);json_file(tmp_path/'request.json',request.data)
    args=['run','--request','request.json'] if mode=='data_only' else ['run','--inputs','inputs.json',
        '--analyzer','example.reviewer','--analyzer','example.second']
    before=inventory(tmp_path)
    with no_write_attempts():result=call(args,tmp_path)
    assert result.exit_code==5
    package=ReportPackage(json.dumps(thaw(result.result)).encode())
    assert len(package.reports)==2
    assert all(r.data['coverage']['open']==r.data['coverage']['expected'] for r in package.reports)
    assert all(r.data['run_status']=='unavailable' for r in package.reports)
    assert result.details['execution_complete'] is result.details['all_languages_confirmed'] is result.details['gate_passed'] is False
    assert inventory(tmp_path)==before


@pytest.mark.parametrize('selected',[['example.reviewer'],['example.reviewer','example.reviewer'],['example.missing']])
def test_request_does_not_silently_filter_or_replace_profile_selection(tmp_path,selected):
    project(tmp_path);json_file(tmp_path/'inputs.json',current_inputs())
    args=['request','--inputs','inputs.json']
    for name in selected:args+=['--analyzer',name]
    with no_write_attempts():result=call(args,tmp_path)
    assert result.exit_code==2


def test_imported_descriptor_cannot_replace_trusted_builtin_identity(tmp_path):
    value=builtin_descriptor().data;value['adapter_version']='2.0.0'
    desc=AnalyzerDescriptor(json.dumps(value).encode())
    profile=dict(analyzers=[analyzer_binding(desc,['language_detection'])],settings={BUILTIN:{}},context=[],extensions={})
    json_file(tmp_path/'inputs.json',profile)
    with no_write_attempts():result=call(['list','--inputs','inputs.json'],tmp_path)
    assert result.exit_code==6


def test_independent_external_settings_change_makes_old_answers_stale(tmp_path):
    _,inputs,_,_,original=observation_files(tmp_path)
    inputs['settings']['example.reviewer']['threshold']='0.7';json_file(tmp_path/'inputs.json',inputs)
    with no_write_attempts():result=call(['evaluate','report.json','--project',str(tmp_path),'--inputs','inputs.json'],tmp_path)
    assert result.exit_code==6
    assert all(r['changed_inputs']==('settings',) for r in result.result['evaluation']['reports'])
    assert (tmp_path/'report.json').read_bytes()==original
