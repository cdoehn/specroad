"""Repeatable immutable evaluation, source races and native read boundaries."""
import json

import pytest

from specroad.analyzers import evaluation
from specroad.analyzers._values import AnalyzerError
from specroad.analyzers.evaluation import evaluate_reports
from specroad.analyzers.packages import create_package
from specroad.analyzers.subjects import request_from_project
from specroad.model.paths import artifact_path
from support.domain import domain_value
from support.read_only import inventory, make_project, no_write_attempts
from support.relations import aid
from test_configuration_scope import configuration, condition
from test_analyzer_evaluation import current_inputs, observations, prepared
from test_partial_read_commands import extracted


def test_reevaluation_retains_original_bytes_and_never_edits_normative_state(tmp_path):
    values, supplied, _, package = prepared(tmp_path)
    raw = json.dumps(package.data, indent=4).encode()
    first = evaluate_reports([raw],project=tmp_path,current_inputs=supplied)
    values[0]['title'] = 'Changed after first evaluation'
    (tmp_path/artifact_path('requirement',values[0]['id'],'SR')).write_text(json.dumps(values[0]))
    before = inventory(tmp_path)
    with no_write_attempts(): second = first.reevaluate(project=tmp_path,current_inputs=supplied)
    assert inventory(tmp_path) == before
    assert first.data['all_reports_current'] and not second.data['all_reports_current']
    assert first.originals == second.originals == (raw,)
    assert [r['report'] for r in first.data['reports']] == [r['report'] for r in second.data['reports']]


def test_reread_without_request_keeps_missing_authority(tmp_path):
    _, supplied, _, package = prepared(tmp_path)
    first = evaluate_reports([package.reports[0].canonical_bytes])
    second = first.reevaluate(project=tmp_path,current_inputs=supplied)
    assert second.data['reports'][0]['currentness'] == 'unavailable'
    assert second.data['reports'][0]['reason'] == 'analyzer_request_unavailable'


@pytest.mark.parametrize('failure', ['change','remove','symlink','io'])
def test_final_native_observation_rejects_changes_and_security_failures(tmp_path,monkeypatch,failure):
    values, supplied, _, package = prepared(tmp_path/'project')
    path = tmp_path/'project'/artifact_path('requirement',values[0]['id'],'SR')
    original_finish = evaluation.ProjectObservation.finish
    original_bytes = path.read_bytes()
    def finish(self):
        if failure == 'change':
            changed = dict(values[0],title='Changed during observation'); path.write_text(json.dumps(changed))
        elif failure == 'remove': path.unlink()
        elif failure == 'symlink':
            target = tmp_path/'outside.json'; target.write_bytes(original_bytes); path.unlink(); path.symlink_to(target)
        else: raise OSError('simulated read failure')
        return original_finish(self)
    monkeypatch.setattr(evaluation.ProjectObservation,'finish',finish)
    result = evaluate_reports([package.original_bytes],project=tmp_path/'project',current_inputs=supplied)
    assert all(r['currentness'] == 'unavailable' for r in result.data['reports'])
    expected = 5 if failure == 'io' else 7 if failure == 'symlink' else 6
    assert all(r['failure_code'] == expected for r in result.data['reports'])
    assert result.originals == (package.original_bytes,)


def test_explicit_current_values_are_owned_before_native_read(tmp_path,monkeypatch):
    _, supplied, _, package = prepared(tmp_path)
    original = evaluation.ProjectObservation.__init__
    def observed(self,*args):
        supplied.clear()
        return original(self,*args)
    monkeypatch.setattr(evaluation.ProjectObservation,'__init__',observed)
    result = evaluate_reports([package.original_bytes],project=tmp_path,current_inputs=supplied)
    assert result.data['all_reports_current']


def test_complete_request_is_current_in_verified_partial_only_for_present_subjects(tmp_path):
    root, _, _, members, hidden = extracted(tmp_path)
    supplied = current_inputs()
    ids = [v['id'] for v in members if v['artifact_type'] == 'requirement']
    assert ids and not set(ids) & {v['id'] for v in hidden}
    request = request_from_project(root,**supplied,subject_ids=ids,analysis_id='partial-currentness')
    package = create_package(request,observations(request))
    before = inventory(root)
    with no_write_attempts(): result = evaluate_reports([package.original_bytes],project=root,current_inputs=supplied)
    assert result.data['all_reports_current'] and inventory(root) == before
    assert all({s['artifact_id'] for s in r['report']['subjects']} == set(ids) for r in result.data['reports'])


@pytest.mark.parametrize('fault', ['context_hash','settings','shape'])
def test_invalid_current_inputs_do_not_impugn_valid_report_integrity(tmp_path,fault):
    _, supplied, _, package = prepared(tmp_path)
    if fault == 'context_hash': supplied['context'][0]['sha256'] = 'f'*64
    elif fault == 'settings': supplied['settings'] = {}
    else: supplied['unexpected'] = True
    with no_write_attempts(): result = evaluate_reports([package.original_bytes],project=tmp_path,current_inputs=supplied)
    assert all(r['currentness'] == 'unavailable' and r['failure_code'] == 3 for r in result.data['reports'])
    assert all(r['report'] is not None and r['request_binding_verified'] for r in result.data['reports'])


def test_reformatting_and_unselected_private_file_do_not_change_original_json_binding(tmp_path):
    values, supplied, _, package = prepared(tmp_path,differing=False)
    path = tmp_path/artifact_path('requirement',values[0]['id'],'SR')
    path.write_text(json.dumps(values[0],indent=4))
    (tmp_path/'private.txt').write_text('Still unselected, not an implicit context resource')
    with no_write_attempts(): result = evaluate_reports([package.original_bytes],project=tmp_path,current_inputs=supplied)
    assert result.data['all_reports_current'] and result.data['disagreements'] == []


@pytest.mark.parametrize('inputs', [[],None,'report.json',[{}],[bytearray(b'{}')]])
def test_invalid_api_selection_never_reads_a_path(inputs):
    with no_write_attempts(),pytest.raises(AnalyzerError) as error:
        evaluate_reports(inputs,project='/never-read')
    assert error.value.exit_code == 2


def test_unknown_namespaces_and_suggestions_cannot_change_evidence_or_execute(tmp_path):
    _, supplied, request, package = prepared(tmp_path)
    before = inventory(tmp_path)
    with no_write_attempts():
        result = evaluate_reports([r.canonical_bytes for r in package.reports], request=request,
                                  project=tmp_path,current_inputs=supplied)
    assert inventory(tmp_path) == before and result.data['all_reports_current']
    assert all(r['report']['findings'][0]['suggestion']['command'] == 'rm -rf /untrusted-example' for r in result.data['reports'])


def test_native_configuration_scope_can_make_otherwise_unchanged_subjects_stale(tmp_path):
    linux = configuration(); windows = configuration(2, selection={'platform':'windows'})
    values = [domain_value('requirement',id=aid(number=i+1),applicability=condition(platform))
              for i,platform in enumerate(('linux','windows'))]
    make_project(tmp_path,linux,windows,*values)
    supplied = current_inputs()
    request = request_from_project(tmp_path,**supplied,configuration_id=linux['id'],analysis_id='configured')
    package = create_package(request,observations(request))
    with no_write_attempts():
        current = evaluate_reports([package.original_bytes],project=tmp_path,current_inputs=supplied,configuration_id=linux['id'])
        stale = current.reevaluate(project=tmp_path,current_inputs=supplied,configuration_id=windows['id'])
    assert current.data['all_reports_current']
    assert all(r['currentness'] == 'stale' for r in stale.data['reports'])
    assert all(r['changed_subject_keys'] == [request.data['subjects'][0]['subject_key']] for r in stale.data['reports'])


def test_absent_subject_in_available_project_is_distinct_from_absent_project(tmp_path):
    values, supplied, _, package = prepared(tmp_path/'project')
    (tmp_path/'project'/artifact_path('requirement',values[0]['id'],'SR')).unlink()
    with no_write_attempts():
        stale = evaluate_reports([package.original_bytes],project=tmp_path/'project',current_inputs=supplied)
        unavailable = evaluate_reports([package.original_bytes],project=tmp_path/'missing',current_inputs=supplied)
    assert all(r['currentness'] == 'stale' for r in stale.data['reports'])
    assert all(r['currentness'] == 'unavailable' for r in unavailable.data['reports'])
