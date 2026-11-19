"""Native CLI results and actual file effects; no presentation or documentation oracle."""
from hashlib import sha256
import json

import pytest

from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.results import thaw
from specroad.cli.request_schema import request_schema
from specroad.model._schema import validate_builtin
from specroad.analyzers.requests import AnalyzerRequest
from specroad.analyzers.packages import ReportPackage
from specroad.model.paths import artifact_path
from support.read_only import inventory, no_write_attempts
from test_analyzer_subjects import project
from test_analyzer_evaluation import prepared

BUILTIN = 'specroad.py3langid'


def call(args, cwd):
    return dispatch_result(['analyzer', *args], cwd=cwd)


def json_file(path, data):
    raw = json.dumps(data, ensure_ascii=False, indent=3).encode()
    path.write_bytes(raw)
    return raw


def outputs(root):
    target = root/'generated'/'analysis'
    target.mkdir(parents=True)
    return target


def observation_files(root):
    values, inputs, request, package = prepared(root)
    original = json_file(root/'report.json', package.data)
    json_file(root/'inputs.json', inputs)
    json_file(root/'request.json', request.data)
    return values, inputs, request, package, original


@pytest.mark.parametrize('name', ['list','describe','request','run','import','show','evaluate'])
def test_all_commands_have_real_registry_classes_and_one_structured_contract(name):
    registry = builtin_registry(); command = registry.resolve('analyzer.'+name)
    assert command.command_class.value == ('generated_output' if name in ('request','run','import') else 'read_only')
    example = command.protocol.example
    validate_builtin(example.as_dict(), request_schema(command))
    bound = registry.bind_request(example)
    assert bound.command.command_id == command.command_id
    assert command.protocol.lock_kind == 'none'
    assert not command.protocol.work.continuation_supported


@pytest.mark.parametrize('args', [['list'],['describe',BUILTIN]])
def test_static_descriptors_need_no_project_or_worker_and_do_not_write(tmp_path, args):
    before = inventory(tmp_path)
    with no_write_attempts(): result = call(args,tmp_path)
    assert result.exit_code == 0
    rows = thaw(result.result)['analyzers']; assert len(rows) == 1
    assert rows[0]['descriptor']['analyzer_id'] == BUILTIN
    assert rows[0]['availability']['execution_supported'] is False
    assert rows[0]['availability']['availability'] == 'not_implemented'
    assert set(rows[0]['schemas']) == {'descriptor','inputs','request','report','package'}
    assert inventory(tmp_path) == before


def test_request_root_discovery_exports_full_separate_values_without_writing(tmp_path):
    values = project(tmp_path); before = inventory(tmp_path)
    with no_write_attempts(): result = call(['request','--analyzer',BUILTIN,'--analysis-id','manual-id'],tmp_path)
    assert result.exit_code == 0
    request = AnalyzerRequest(json.dumps(thaw(result.result)).encode()).data
    assert request['request_id'] == 'manual-id'
    assert [s['value'] for s in request['subjects']] == [v['statement'] for v in values]
    assert request['settings'][BUILTIN]['language_detection']['min_text_codepoints'] == 20
    assert 'UNSELECTED SECRET' not in json.dumps(request)
    assert inventory(tmp_path) == before


def test_explicit_subject_and_field_remain_separate_original_values(tmp_path):
    values = project(tmp_path)
    result = call(['request','--analyzer',BUILTIN,'--subject',values[1]['id'],
                   '--field','/statement','--field','/title','--analysis-id','chosen'],tmp_path)
    assert result.exit_code == 0
    subjects = thaw(result.result)['subjects']
    assert len(subjects) == 2 and {s['artifact_id'] for s in subjects} == {values[1]['id']}
    assert [s['field_pointer'] for s in subjects] == ['/statement','/title']


def test_request_file_is_exact_complete_jcs_and_only_generated_data_changes(tmp_path):
    project(tmp_path); target = outputs(tmp_path); before = inventory(tmp_path)
    result = call(['request','--analyzer',BUILTIN,'--analysis-id','file','--output','request.json'],tmp_path)
    assert result.exit_code == 0
    request = AnalyzerRequest((target/'request.json').read_bytes())
    assert request.data == thaw(result.result) and request.canonical_bytes == (target/'request.json').read_bytes()
    assert result.details['publication']['changed'] is True
    assert not (tmp_path/'.specroad').exists()
    assert [row for row in inventory(tmp_path) if row[0] != 'generated/analysis/request.json'] == list(before)


@pytest.mark.parametrize('from_file', [False,True])
def test_run_delivers_complete_unavailable_package_without_worker_or_false_success(tmp_path, from_file):
    project(tmp_path)
    request = call(['request','--analyzer',BUILTIN,'--analysis-id','unavailable'],tmp_path)
    json_file(tmp_path/'request.json',thaw(request.result))
    args = ['run','--request','request.json'] if from_file else ['run','--analyzer',BUILTIN]
    before = inventory(tmp_path)
    with no_write_attempts(): result = call(args,tmp_path)
    assert result.exit_code == 5
    package = ReportPackage(json.dumps(thaw(result.result)).encode())
    assert len(package.reports) == 1
    report = package.reports[0].data
    assert report['run_status'] == 'unavailable'
    assert report['coverage']['open'] == report['coverage']['expected']
    assert report['operational']['execution_supported'] is False
    assert inventory(tmp_path) == before


def test_unavailable_run_can_publish_valid_complete_package(tmp_path):
    project(tmp_path); target = outputs(tmp_path)
    result = call(['run','--analyzer',BUILTIN,'--output','unavailable.json'],tmp_path)
    assert result.exit_code == 5
    package = ReportPackage((target/'unavailable.json').read_bytes())
    assert package.data == thaw(result.result)


def test_import_preserves_original_bytes_including_whitespace_and_separate_evaluation(tmp_path):
    *_, original = observation_files(tmp_path); target = outputs(tmp_path)
    result = call(['import','report.json','--project',str(tmp_path),'--output','imported.json'],tmp_path)
    assert result.exit_code == 0 and (target/'imported.json').read_bytes() == original
    data = thaw(result.result)
    assert data['sources'][0]['sha256'] == sha256(original).hexdigest()
    assert all(r['currentness'] == 'unavailable' for r in data['evaluation']['reports'])
    assert data['gate_passed'] is False and data['approval_granted'] is False


def test_show_and_evaluate_are_read_only_with_independent_current_inputs(tmp_path):
    observation_files(tmp_path); before = inventory(tmp_path)
    with no_write_attempts():
        shown = call(['show','report.json','--project',str(tmp_path),'--inputs','inputs.json'],tmp_path)
        evaluated = call(['evaluate','report.json','report.json','--project',str(tmp_path),'--inputs','inputs.json'],tmp_path)
    assert shown.exit_code == 0 and evaluated.exit_code == 0
    result = thaw(evaluated.result)
    assert len(result['sources']) == 2 and len(result['evaluation']['reports']) == 4
    assert result['current_check_passed'] and result['execution_complete'] and result['gate_passed']
    assert inventory(tmp_path) == before


def test_variadic_structured_inputs_preserve_order_and_match_cli(tmp_path):
    observation_files(tmp_path)
    request = {'command_id':'analyzer.evaluate','arguments':{'files':['report.json','report.json']}}
    native = execute_request(request,cwd=tmp_path).result
    cli = call(['evaluate','report.json','report.json'],tmp_path)
    assert native.exit_code == cli.exit_code == 5
    assert thaw(native.result)['evaluation'] == thaw(cli.result)['evaluation']


def test_currentness_fails_on_original_artifact_change_without_mutating_report(tmp_path):
    values, _, _, _, original = observation_files(tmp_path)
    values[0]['title'] = 'Changed original title'
    json_file(tmp_path/artifact_path('requirement',values[0]['id'],'SR'),values[0])
    result = call(['evaluate','report.json','--project',str(tmp_path),'--inputs','inputs.json'],tmp_path)
    assert result.exit_code == 6 and not result.result['gate_passed']
    assert (tmp_path/'report.json').read_bytes() == original


def test_corrupt_selected_report_is_not_hidden_by_another_valid_input(tmp_path):
    observation_files(tmp_path); (tmp_path/'bad.json').write_bytes(b'{')
    result = call(['evaluate','bad.json','report.json'],tmp_path)
    assert result.exit_code == 3
    rows = thaw(result.result)['evaluation']['reports']
    assert len(rows) == 3 and rows[0]['currentness'] == 'invalid'
    assert [r['input_index'] for r in rows] == [0,1,1]


def test_single_report_import_requires_request_but_show_is_honestly_unavailable(tmp_path):
    _, _, request, package, _ = observation_files(tmp_path)
    json_file(tmp_path/'single.json',package.reports[0].data)
    assert call(['import','single.json'],tmp_path).exit_code == 3
    shown = call(['show','single.json'],tmp_path)
    assert shown.exit_code == 0 and not shown.result['gate_passed']
    imported = call(['import','single.json','--request','request.json'],tmp_path)
    assert imported.exit_code == 0
    assert imported.result['evaluation']['reports'][0]['report']['request_id'] == request.data['request_id']
