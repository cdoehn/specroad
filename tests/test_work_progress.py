"""Measured windows execute or reuse real durable minimum handler work."""

from dataclasses import FrozenInstanceError
import errno
import json
import subprocess
import sys

import pytest

from specroad.cli.application import execute_request
from specroad.cli.requests import CommandRequest
from specroad.runtime.consumption import CounterSample, ConsumptionError, WorkConsumption
from specroad.work.checkpoints import CheckpointStorageError
from specroad.work.progress import ReadOnlyWorkWindow, advance_read_only_work
from specroad.work.resume import WorkResumeError
from support.read_only import inventory, no_write_attempts
from test_work_resume import recorded, setup, REQUESTS, ROOT, PORTABLE


def ticking():
    value = 0
    def sample():
        nonlocal value
        value += 10_000_000
        return CounterSample(value, value, None, 'fixture:cpu', 'fixture:wall', 'unknown')
    return sample


def unknown():
    return CounterSample(None, None, None)


def window(store, ledger, options=None, *, cwd=None):
    call = ledger.begin(options)
    try:
        result = advance_read_only_work(store, call, cwd=cwd)
    finally:
        report = call.finish()
    return result, report


@pytest.mark.parametrize('command_request', REQUESTS, ids=lambda value: value.command_id)
@pytest.mark.parametrize('flag', ['--cpu-budget-ms', '--wall-budget-ms', '--step-cpu-ms', '--step-wall-ms'])
def test_exceeded_soft_window_still_confirms_the_actual_complete_minimum_unit(recorded, tmp_path, command_request, flag):
    initial, roots, _, store = setup(tmp_path, command_request)
    expected = execute_request(command_request, cwd=tmp_path).result.as_dict()
    protected = inventory(roots[0].root)
    result, report = window(store, WorkConsumption(sampler=ticking()), {flag: 1}, cwd=tmp_path)
    value = result.as_dict();step = value['step']
    assert value['observations']['before']['soft_budget_exceeded'] is True
    assert value['soft_budget_exceeded'] and value['smallest_unit_attempted']
    assert value['progress_made'] and value['checkpoint_changed']
    assert value['previous_checkpoint_generation'] == 0 and step['checkpoint_generation'] == 1
    assert value['previous_checkpoint_sha256'] == initial.as_dict()['checkpoint_sha256']
    assert value['new_completed_unit_ids'] == [initial.entries('remaining')[0]['unit_id']]
    assert value['reused_completed_unit_ids'] == []
    assert step['command_outcome'] == expected and step['command_exit_code'] == 0
    assert step['work_state'] == 'running' and value['global_finalization_required'] is True
    assert step['next_action']['operation'] == 'finalize_declared_work'
    assert store.read().raw == result.step.manifest.raw and inventory(roots[0].root) == protected
    assert report['invocation']['controls']['phases']['work_unit'] == {'start': 1, 'end': 1}
    assert report['soft_budget_exceeded'] and value['consumption_persisted'] is False


def test_new_resource_profile_reuses_confirmed_result_without_an_empty_generation(recorded, tmp_path, monkeypatch):
    initial, roots, location, store = setup(tmp_path)
    first, _ = window(store, WorkConsumption(sampler=ticking()), {'--step-wall-ms': 1})
    before = inventory(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError('confirmed handler prefix executed again')
    monkeypatch.setattr('specroad.work.resume.execute_request', forbidden)
    ledger = WorkConsumption(sampler=unknown)
    for options in ({'--resource-profile': 'standard'}, {'--step-cpu-ms': 1}, {'--wall-budget-ms': 999999}):
        again, report = window(store, ledger, options)
        value = again.as_dict()
        assert not value['progress_made'] and not value['checkpoint_changed']
        assert not value['smallest_unit_attempted'] and value['new_completed_unit_ids'] == []
        assert value['reused_completed_unit_ids'] == first.as_dict()['new_completed_unit_ids']
        assert value['previous_checkpoint_generation'] == value['step']['checkpoint_generation'] == 1
        assert value['previous_checkpoint_sha256'] == value['step']['checkpoint_sha256']
        assert again.step.manifest.raw == first.step.manifest.raw
        assert again.step.outcome_bytes == first.step.outcome_bytes
        assert value['window_reason'] == 'reuse_completed_unit' and inventory(tmp_path) == before
    assert report['invocations_recorded'] == 3


def test_unknown_measurements_do_not_invent_exhaustion_or_block_execution(recorded, tmp_path):
    _, _, _, store = setup(tmp_path)
    result, report = window(store, WorkConsumption(sampler=unknown), {'--step-cpu-ms': 1})
    assert result.step.executed and not result.as_dict()['soft_budget_exceeded']
    assert report['invocation']['measured']['cpu_ns']['value'] is None
    assert result.as_dict()['observations']['after']['measured']['wall_ns']['value'] is None


def test_exceeded_target_after_execution_keeps_the_complete_durable_unit(recorded, tmp_path):
    _, _, _, store = setup(tmp_path)
    values = iter([0, 500_000, 2_000_000, 3_000_000])
    ledger = WorkConsumption(sampler=lambda: CounterSample(next(values), None, None))
    result, report = window(store, ledger, {'--step-cpu-ms': 1})
    value = result.as_dict()
    assert not value['observations']['before']['soft_budget_exceeded']
    assert value['observations']['after']['soft_budget_exceeded'] and value['progress_made']
    assert store.read().raw == result.step.manifest.raw and report['soft_budget_exceeded']


def test_window_projections_are_detached_and_cannot_change_confirmed_work(recorded, tmp_path):
    _, _, _, store = setup(tmp_path)
    result, _ = window(store, WorkConsumption(sampler=ticking()), {'--step-wall-ms': 1})
    before = store.read().raw;value = result.as_dict()
    value['new_completed_unit_ids'].clear()
    value['observations']['before']['measured']['cpu_ns']['value'] = 0
    value['step']['command_outcome']['command'] = 'foreign'
    assert result.as_dict()['new_completed_unit_ids']
    assert result.as_dict()['observations']['before']['measured']['cpu_ns']['value'] > 0
    assert store.read().raw == before and result.step.as_dict()['command_outcome']['command'] == 'version'
    with pytest.raises(FrozenInstanceError):
        result.step = None
    with pytest.raises(TypeError):
        ReadOnlyWorkWindow()


@pytest.mark.parametrize('invalid', [None, {}, 'foreign'])
def test_unowned_measurement_cannot_start_or_change_work(recorded, tmp_path, invalid):
    _, _, _, store = setup(tmp_path);before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ConsumptionError):
        advance_read_only_work(store, invalid)
    assert inventory(tmp_path) == before


def test_finished_measurement_window_cannot_confirm_progress(recorded, tmp_path):
    _, _, _, store = setup(tmp_path);before = inventory(tmp_path)
    call = WorkConsumption(sampler=unknown).begin();call.finish()
    with no_write_attempts(), pytest.raises(ConsumptionError):
        advance_read_only_work(store, call)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('invalid', [None, {}])
def test_untrusted_work_is_rejected_before_measurement_or_mutation(invalid):
    call = WorkConsumption(sampler=unknown).begin()
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        advance_read_only_work(invalid, call)
    assert caught.value.reason == 'trusted_work_store_required'
    assert call.finish()['invocation']['controls']['checks'] == 0


def test_incomplete_handler_cannot_become_progress_due_to_a_tiny_window(recorded, tmp_path):
    initial, _, location, store = setup(tmp_path,
        CommandRequest('schema.show', arguments={'schema_id': 'missing-schema'}))
    before = inventory(location.path);call = WorkConsumption(sampler=ticking()).begin({'--step-cpu-ms': 1})
    try:
        with pytest.raises(WorkResumeError) as caught:
            advance_read_only_work(store, call)
    finally:
        report = call.finish()
    assert caught.value.reason == 'command_did_not_complete' and caught.value.exit_code == 2
    assert store.read().raw == initial.raw and inventory(location.path) == before
    assert report['invocation']['controls']['phases']['work_unit'] == {'start': 1, 'end': 0}


def test_publication_failure_preserves_prior_generation_without_a_success_window(recorded, tmp_path, monkeypatch):
    initial, _, location, store = setup(tmp_path)
    before = {p:p.read_bytes() for p in location.path.rglob('*') if p.is_file()}
    def unavailable(*args, **kwargs):
        raise OSError(errno.ENOSPC, 'labelled real write failure')
    call = WorkConsumption(sampler=ticking()).begin({'--step-cpu-ms': 1})
    try:
        with monkeypatch.context() as scoped:
            scoped.setattr('specroad.work.checkpoints._write_new', unavailable)
            with pytest.raises(OSError) as caught:
                advance_read_only_work(store, call)
    finally:
        report = call.finish()
    assert caught.value.errno == errno.ENOSPC
    assert store.read().raw == initial.raw
    assert all(p.read_bytes() == raw for p,raw in before.items())
    assert report['invocation']['controls']['phases']['work_unit']['end'] == 0


def test_missing_checkpoint_bytes_never_turn_into_empty_progress(recorded, tmp_path, monkeypatch):
    _, _, location, store = setup(tmp_path)
    pointer = json.loads((location.path / 'work.json').read_bytes())
    (location.path / 'checkpoints' / (pointer['checkpoint']['sha256'] + '.json')).unlink()
    before = inventory(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError('missing work executed')
    monkeypatch.setattr('specroad.work.resume.execute_request', forbidden)
    call = WorkConsumption(sampler=ticking()).begin({'--step-wall-ms': 1})
    try:
        with no_write_attempts(), pytest.raises(CheckpointStorageError):
            advance_read_only_work(store, call)
    finally:
        call.finish()
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('kind', ['module', 'zipapp'])
def test_new_built_process_reuses_small_window_result_after_relocation(tmp_path, kind):
    output = tmp_path / 'distribution'
    built = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'tools/build_core.py'),
                            '--output', str(output)], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    distribution = output / ('module' if kind == 'module' else 'specroad.pyz')
    packet,work,project = (tmp_path / name for name in ('binding.json','work','project'))
    project.mkdir()
    replacement = ''' from specroad.work.progress import advance_read_only_work
 from specroad.runtime.consumption import WorkConsumption,CounterSample
 samples=iter([0,10000000,20000000,30000000])
 call=WorkConsumption(sampler=lambda:CounterSample(next(samples),None,None)).begin({'--step-cpu-ms':1})
 try:
  step=advance_read_only_work(store,call,cwd=project)
 finally:
  call.finish()'''
    code = PORTABLE.replace(' step=resume_read_only_work(store,cwd=project)', replacement)
    assert code != PORTABLE
    def invoke(action):
        prefix = 'import sys;sys.path.insert(0,' + repr(str(distribution)) + ');'
        result = subprocess.run([sys.executable,'-I','-B','-c',prefix+code,
            str(packet),str(work),str(project),action],capture_output=True,text=True)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    initial = invoke('plan');first = invoke('resume');before = inventory(project)
    new = tmp_path / ('moved-module' if kind == 'module' else 'moved.pyz')
    distribution.rename(new);distribution = new
    work.rename(tmp_path / 'moved-work');work = tmp_path / 'moved-work'
    project.rename(tmp_path / 'moved-project');project = tmp_path / 'moved-project'
    stored = inventory(work);again = invoke('resume')
    assert first['soft_budget_exceeded'] and first['progress_made'] and not again['progress_made']
    assert first['step']['work_id'] == again['step']['work_id'] == initial['work_id']
    assert first['step']['checkpoint_sha256'] == again['step']['checkpoint_sha256']
    assert first['step']['command_outcome'] == again['step']['command_outcome']
    assert first['new_completed_unit_ids'] == again['reused_completed_unit_ids']
    assert inventory(project) == before and inventory(work) == stored
