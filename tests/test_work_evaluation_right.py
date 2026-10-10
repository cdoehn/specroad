"""Bound retained observations, real missing inputs and current host boundaries."""

import errno
import json
from pathlib import Path

import pytest

from specroad import _build
from specroad.work import evaluation
from specroad.work.evaluation import (WorkEvaluationBlocked, WorkEvaluationDataError,
                                     finalize_evaluation_work)
from specroad.work.manifest import complete_work_manifest
from specroad.work.resume import WorkResumeError
from support.read_only import inventory, no_write_attempts
from support.command_parity import build_core, process_environment, run_python
from support.work_evaluation import setup, data, registry, advance, direct, PORTABLE, failed_inputs, run, copy_record
from test_work_resume import recorded


@pytest.mark.parametrize('operation', ['advance', 'finalize'])
@pytest.mark.parametrize('change', ['missing_stage', 'unknown_stage', 'incomplete_phase',
    'missing_dependency', 'changed_selection', 'source_binding', 'duplicate_source',
    'approval', 'model_result', 'lost_diagnostic', 'diagnostic_summary',
    'diagnostic_format', 'lost_native_finding', 'extra_projection'])
def test_self_hashed_observations_cannot_drop_phases_scope_or_findings(recorded, tmp_path, monkeypatch, operation, change):
    inputs, jobs, _ = failed_inputs()
    original = setup(tmp_path / 'actual', input_data=inputs, job_data=jobs)
    def mutate(row):
        observation = row['observation']; report = observation['source_report']
        if change == 'missing_stage': report['stages'].pop()
        elif change == 'unknown_stage': report['stages'][4]['stage'] = 'foreign'
        elif change == 'incomplete_phase': report['stages'][5]['status'] = 'unavailable'
        elif change == 'missing_dependency': report['stages'][4]['checked_ids'].pop(0)
        elif change == 'changed_selection': report['requested_ids'] = []
        elif change == 'source_binding': report['source_bindings'][0]['sha256'] = '0' * 64
        elif change == 'duplicate_source': report['identified_sources'][1] = dict(report['identified_sources'][0])
        elif change == 'approval': report['approval_granted'] = True
        elif change == 'model_result': report['model_valid'] = True
        elif change == 'lost_diagnostic': row['diagnostics'] = []; observation['diagnostics'] = []
        elif change == 'diagnostic_summary': observation['summary']['diagnostic_count'] = 0
        elif change == 'diagnostic_format': observation['diagnostic_format_version'] = 2
        elif change == 'lost_native_finding': report['stages'][5]['diagnostics'].pop()
        else: observation['undeclared_result_field'] = True
    store, candidate = copy_record(tmp_path, original, mutate)
    def forbidden(*args, **kwargs): raise AssertionError('Unverified work reached native execution')
    monkeypatch.setattr(evaluation, '_evaluate', forbidden)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught: run(store, operation)
    assert caught.value.reason == 'invalid_evaluation_completion' and caught.value.exit_code == 6
    assert store.read().raw == candidate.raw and inventory(tmp_path) == before


@pytest.mark.parametrize('operation', ['advance', 'finalize'])
@pytest.mark.parametrize('change', ['format', 'missing_value', 'unknown_state', 'boolean_code', 'malformed_diagnostic'])
def test_invalid_srx_completion_is_a_conflict_before_writes(recorded, tmp_path, operation, change):
    inputs, jobs, _ = data(); original = setup(tmp_path / 'actual', input_data=inputs, job_data=[jobs[1]])
    def mutate(row):
        if change == 'format': row['format_version'] = 'future-unit'
        elif change == 'missing_value': row['observation'].pop('value')
        elif change == 'unknown_state': row['observation']['value_state'] = 'future'
        elif change == 'boolean_code': row['exit_code'] = False
        else: row['diagnostics'] = [{'code': 'SRV110'}]
    store, candidate = copy_record(tmp_path, original, mutate); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught: run(store, operation)
    assert caught.value.exit_code == 6 and inventory(tmp_path) == before
    assert store.read().raw == candidate.raw


@pytest.mark.parametrize('kind', ['model', 'profiles'])
@pytest.mark.parametrize('change', ['missing', 'changed'])
def test_lost_captured_bytes_name_the_resource_without_original_source_fallback(recorded, tmp_path, kind, change):
    _, _, _, _, _, initial, location, store = setup(tmp_path); advance(store)
    item = next(row for row in initial.entries('inputs') if row['root_id'] == kind)
    path = location.path / 'objects' / item['sha256']
    if change == 'missing': path.unlink()
    else: path.write_bytes(path.read_bytes() + b' ')
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkEvaluationDataError) as caught: advance(store)
    assert caught.value.exit_code == 6
    expected = {k: item[k] for k in ('root_id', 'path', 'sha256')}
    assert caught.value.as_dict()['resource'] == expected
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('kind', ['missing_dependency', 'malformed_outside_selection'])
def test_incomplete_required_input_set_retains_all_findings_and_no_confirmed_unit(recorded, tmp_path, kind):
    inputs, jobs, _ = data()
    if kind == 'missing_dependency': inputs.pop(1)
    else:
        inputs[0]['raw'] = b'{broken'; inputs[3]['raw'] = b'{another-broken'
    _, _, _, project, _, initial, _, store = setup(tmp_path, input_data=inputs, job_data=jobs)
    before = inventory(project)
    with pytest.raises(WorkEvaluationBlocked) as caught: advance(store)
    observed = caught.value.as_dict()['observation']
    assert observed == direct(inputs, jobs[:1])[0]['observation']
    assert caught.value.exit_code == 3 and observed['checks_complete'] is False
    assert len(observed['diagnostics']) >= (1 if kind == 'missing_dependency' else 2)
    assert store.read().raw == initial.raw and inventory(project) == before


@pytest.mark.parametrize('boundary', ['evaluation', 'publication'])
def test_late_build_change_preserves_the_actual_durable_prefix(recorded, tmp_path, monkeypatch, boundary):
    inputs, jobs, _, _, _, initial, _, store = setup(tmp_path)
    original = dict(_build.BUILD_METADATA)
    def change(): monkeypatch.setattr(_build, 'BUILD_METADATA', {**original, 'build_sha256': 'b' * 64})
    with monkeypatch.context() as scoped:
        if boundary == 'evaluation':
            native = evaluation._evaluate
            def altered(*args, **kwargs):
                value = native(*args, **kwargs); change(); return value
            scoped.setattr(evaluation, '_evaluate', altered)
        else:
            from specroad.work import checkpoints
            native = checkpoints.replace_bound_image
            def altered(*args, **kwargs):
                value = native(*args, **kwargs); change(); return value
            scoped.setattr(checkpoints, 'replace_bound_image', altered)
        with pytest.raises(WorkResumeError) as caught: advance(store)
    assert caught.value.exit_code == 6 and caught.value.reason == 'runtime_build_changed'
    retained = store.read()
    assert retained.as_dict()['checkpoint_generation'] == (0 if boundary == 'evaluation' else 1)
    monkeypatch.setattr(_build, 'BUILD_METADATA', original)
    native = evaluation._evaluate; completed = {row['unit_id'] for row in retained.entries('completed')}
    def remaining(current, task, call):
        assert task['unit_id'] not in completed
        return native(current, task, call)
    monkeypatch.setattr(evaluation, '_evaluate', remaining)
    while store.read().entries('remaining'): advance(store)
    assert json.loads(finalize_evaluation_work(store, registry=registry()).outcome_bytes)['result']['results'] == direct(inputs, jobs)


@pytest.mark.parametrize('operation', ['advance', 'finalize'])
@pytest.mark.parametrize('change', ['drop_result', 'drop_diagnostic'])
def test_global_completion_cannot_discard_an_actual_unit_or_diagnostic(recorded, tmp_path, operation, change):
    inputs, jobs, _ = failed_inputs(); *_, store = setup(tmp_path, input_data=inputs, job_data=jobs)
    while store.read().entries('remaining'): advance(store)
    current = store.read(); actual = evaluation._outcome(current); document = actual.as_dict()
    if change == 'drop_result': document['result']['results'].pop()
    else: document['diagnostics'].pop()
    candidate = complete_work_manifest(current, document, exit_code=actual.exit_code)
    store.publish(candidate); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught: run(store, operation)
    assert caught.value.reason == 'evaluation_final_result_changed' and caught.value.exit_code == 6
    assert store.read().raw == candidate.raw and inventory(tmp_path) == before


def test_saved_native_results_are_rechecked_without_reexecuting_evaluators(recorded, tmp_path, monkeypatch):
    inputs, jobs, _ = failed_inputs(); *_, store = setup(tmp_path, input_data=inputs, job_data=jobs)
    while store.read().entries('remaining'): advance(store)
    expected = finalize_evaluation_work(store, registry=registry()); before = inventory(tmp_path)
    def forbidden(*args, **kwargs): raise AssertionError('A confirmed Fach evaluation ran again')
    monkeypatch.setattr(evaluation, '_evaluate', forbidden)
    monkeypatch.setattr('specroad.validation.validate_model', forbidden)
    monkeypatch.setattr('specroad.profiles.composition.compose_profiles', forbidden)
    monkeypatch.setattr(evaluation, 'load_srx_graph', forbidden)
    monkeypatch.setattr(evaluation, 'evaluate_srx', forbidden)
    assert advance(store)[0].executed_unit_ids == ()
    assert finalize_evaluation_work(store, registry=registry()).outcome_bytes == expected.outcome_bytes
    assert inventory(tmp_path) == before


def test_fresh_host_descriptor_limits_preserve_checkpoint_and_allow_later_progress(tmp_path):
    inputs, jobs, _ = data(); project = tmp_path / 'project'
    for item in inputs:
        p = project / item['root_id'] / item['path']; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(item['raw'])
    packet = tmp_path / 'independent-binding.json'
    packet.write_text(json.dumps({'inputs': [{**i, 'raw': i['raw'].hex()} for i in inputs], 'jobs': jobs}))
    output = tmp_path / 'distribution'; root = Path(__file__).resolve().parents[1]
    built = build_core(root, output)
    assert built.returncode == 0, built.stderr
    work = tmp_path / 'work'; environment = process_environment()
    def invoke(action, limit=32):
        body = PORTABLE.replace('store=CheckpointStore(location,initial)',
            'store=CheckpointStore(location,initial)\nimport resource\nresource.setrlimit(resource.RLIMIT_NOFILE,('+str(limit)+',resource.getrlimit(resource.RLIMIT_NOFILE)[1]))')
        wrapper = ('import sys,json,errno;sys.path.insert(0,' + repr(str(output / 'module')) + ')\n'
            'try:\n exec(' + repr(body) + ')\n'
            'except OSError as error:\n print(json.dumps({"native_errno":error.errno}));raise SystemExit(19)\n')
        child = run_python(wrapper, [str(packet), str(work), str(project), action, 'constrained'],
            cwd=tmp_path, environment=environment)
        assert child.returncode in (0, 19), child.stderr
        return child.returncode, json.loads(child.stdout)
    assert invoke('plan')[0] == 0
    code, first = invoke('advance'); assert code == 0 and first['generation'] == 1
    before = inventory(work); project_before = inventory(project)
    code, failure = invoke('advance', 4)
    assert code == 19 and failure == {'native_errno': errno.EMFILE}
    assert inventory(work) == before and inventory(project) == project_before
    seen = set(first['executed'])
    for index in range(1, len(jobs)):
        code, step = invoke('advance', 32 if index % 2 else 64)
        assert code == 0 and step['generation'] == index + 1 and not seen.intersection(step['executed'])
        seen.update(step['executed'])
    code, final = invoke('finalize')
    assert code == 0 and len(seen) == len(jobs)
    assert final['outcome']['result']['results'] == direct(inputs, jobs)
    assert inventory(project) == project_before
