"""Measured soft windows preserve real complete spool work and protected data."""

import errno
import os

import pytest

from specroad.diagnostics import diagnostic_key
from specroad.diagnostics.spooling import DiagnosticSort, create_diagnostic_spool
from specroad.graph.path_output import PathSort
from specroad.runtime.adaptive_spooling import advance_spool_sort
from specroad.runtime.consumption import CounterSample, ConsumptionError, WorkConsumption
from support.read_only import inventory
from test_spooling_right import roots, diagnostics, delivered, layered_paths, pause_in_merge


def ticking():
    value = 0
    def sample():
        nonlocal value
        value += 10_000_000
        return CounterSample(value, value, None, 'fixture:cpu', 'fixture:wall', 'unknown')
    return sample


def unknown():
    return CounterSample(None, None, None)


def window(task, ledger, options=None, *, max_units=256):
    call = ledger.begin(options)
    try:
        result = advance_spool_sort(task, call, max_units=max_units)
    finally:
        report = call.finish()
    return result, report


def finish(task, ledger, options=None, *, max_units=256):
    windows = []
    for _ in range(10000):
        previous = task.state['units_completed']
        result, report = window(task, ledger, options, max_units=max_units)
        windows.append((result, report))
        assert result['units_completed'] == task.state['units_completed'] - previous
        assert result['progress_made'] and 0 < result['units_completed'] <= max_units
        assert result['checkpoint'] is None and not result['durable_checkpoint']
        assert result['continuation_scope'] == 'same_live_task_in_current_process'
        if result['state'] == 'completed':
            assert result['next_action'] == 'read_complete_spool'
            return task.result, windows
        assert result['state'] == 'active' and result['next_action'] == 'advance_same_live_sort'
        with pytest.raises(ValueError):
            _ = task.result
    raise AssertionError('A finite fixture did not complete with positive work')


@pytest.mark.parametrize('flag', ['--cpu-budget-ms', '--wall-budget-ms', '--step-cpu-ms', '--step-wall-ms'])
def test_already_exceeded_tiny_target_still_completes_one_real_unit_per_window(tmp_path, flag):
    protected = roots(tmp_path)
    before = inventory(protected[0].root)
    consumed = []
    def once():
        for index, value in enumerate(diagnostics(37)):
            consumed.append(index)
            yield value
    ledger = WorkConsumption(sampler=ticking())
    with DiagnosticSort(tmp_path / 'spool', once(), protected_roots=protected, batch_bytes=2**20) as task:
        spool, windows = finish(task, ledger, {flag: 1}, max_units=1000)
        assert all(result['units_completed'] == 1 and result['soft_budget_exceeded'] for result, report in windows)
        assert windows[0][0]['cursor']['accepted_records'] == 1
        assert windows[0][0]['adaptation']['batch_bytes_after'] == 65536
        assert all(result['adaptation']['smallest_unit_attempted'] for result, report in windows)
        assert all(report['invocation']['controls']['phases']['spool_unit'] == {'start': 1, 'end': 1}
                   for result, report in windows)
        assert consumed == list(range(37))
        assert delivered(spool, 3) == sorted(diagnostics(37), key=diagnostic_key)
        final_report = windows[-1][1]
        assert final_report['invocations_recorded'] == len(windows)
        assert final_report['cumulative']['measured']['cpu_ns']['value'] > 0
    assert inventory(protected[0].root) == before


@pytest.mark.parametrize('units', [1, 7, 1000])
def test_unknown_measurements_allow_bounded_progress_without_invented_exhaustion(tmp_path, units):
    protected = roots(tmp_path)
    with DiagnosticSort(tmp_path / 'spool', diagnostics(23), protected_roots=protected, batch_bytes=700) as task:
        spool, windows = finish(task, WorkConsumption(sampler=unknown), max_units=units)
        assert all(not result['soft_budget_exceeded'] for result, report in windows)
        assert all(report['invocation']['measured']['cpu_ns']['value'] is None for result, report in windows)
        assert delivered(spool, 1) == sorted(diagnostics(23), key=diagnostic_key)
        assert windows[0][0]['adaptation']['batch_bytes_after'] == 700


def test_soft_target_observed_after_work_stops_at_that_completed_unit(tmp_path):
    protected = roots(tmp_path)
    observations = iter([0, 500000, 2000000, 3000000])
    ledger = WorkConsumption(sampler=lambda: CounterSample(next(observations), None, None))
    with DiagnosticSort(tmp_path / 'spool', diagnostics(8), protected_roots=protected, batch_bytes=2**20) as task:
        result, report = window(task, ledger, {'--cpu-budget-ms': 1}, max_units=1000)
        assert result['units_completed'] == 1 and result['cursor']['accepted_records'] == 1
        assert result['soft_budget_exceeded'] and report['soft_budget_exceeded']
        assert task.batch_bytes == 65536 and result['state'] == 'active'


def test_memory_event_reduces_future_batches_without_losing_buffered_or_pending_input(tmp_path):
    protected = roots(tmp_path)
    with DiagnosticSort(tmp_path / 'spool', diagnostics(25), protected_roots=protected, batch_bytes=700) as task:
        for _ in range(100):
            previous = task.advance(1)
            if previous['pending_input_sequence'] is not None:
                break
            assert not previous['complete']
        assert previous['buffered_records'] > 0
        assert previous['pending_input_sequence'] == previous['accepted_records']
        ledger = WorkConsumption(sampler=unknown)
        call = ledger.begin({'--memory-budget-mib': 1})
        call.account_bytes('memory', 2 * 1024**2)
        try:
            result = advance_spool_sort(task, call)
        finally:
            call.account_bytes('memory', 2 * 1024**2, release=True)
            report = call.finish()
        assert result['units_completed'] == 1 and result['soft_budget_exceeded']
        assert task.batch_bytes == 1
        assert result['cursor']['accepted_records'] == previous['accepted_records']
        assert result['cursor']['pending_input_sequence'] == previous['pending_input_sequence']
        assert report['invocation']['accounted']['memory_peak_bytes']['value'] == 2 * 1024**2
        spool, windows = finish(task, ledger)
        assert delivered(spool, 2) == sorted(diagnostics(25), key=diagnostic_key)
        assert spool.manifest['batch']['peak_records'] >= previous['buffered_records']
        assert spool.manifest['batch']['target_bytes'] == 1


def test_tiny_windows_and_large_window_produce_identical_complete_record_bytes(tmp_path):
    protected = roots(tmp_path)
    with create_diagnostic_spool(tmp_path / 'reference', diagnostics(29), protected_roots=protected) as reference:
        expected = (tmp_path / 'reference' / reference.manifest['result']['name']).read_bytes()
    with DiagnosticSort(tmp_path / 'adaptive', diagnostics(29), protected_roots=protected, batch_bytes=2**20) as task:
        spool, windows = finish(task, WorkConsumption(sampler=ticking()), {'--step-wall-ms': 1})
        actual = (tmp_path / 'adaptive' / spool.manifest['result']['name']).read_bytes()
        assert actual == expected
        assert spool.manifest['record_count'] == 29


def test_existing_open_merge_advances_its_cursor_instead_of_restarting(tmp_path):
    protected = roots(tmp_path)
    with DiagnosticSort(tmp_path / 'spool', diagnostics(25), protected_roots=protected, batch_bytes=1) as task:
        previous = pause_in_merge(task)
        output = previous['operation']['output']
        result, report = window(task, WorkConsumption(sampler=ticking()), {'--step-cpu-ms': 1})
        current = result['cursor']['operation']['output']
        assert current['name'] == output['name']
        assert current['records_written'] >= output['records_written']
        assert result['cursor']['units_completed'] == previous['units_completed'] + 1
        spool, windows = finish(task, WorkConsumption(sampler=unknown))
        assert delivered(spool, 1) == sorted(diagnostics(25), key=diagnostic_key)


def test_prepared_paths_keep_order_and_duplicates_under_tiny_measured_windows(tmp_path):
    protected = roots(tmp_path)
    paths, _ = layered_paths(3)
    expected = list(reversed(paths)) + paths[:2]
    with PathSort(tmp_path / 'paths', iter(expected), protected_roots=protected) as task:
        spool, windows = finish(task, WorkConsumption(sampler=ticking()), {'--step-wall-ms': 1})
        assert delivered(spool, 2) == expected
        assert all(result['units_completed'] == 1 for result, report in windows)


def test_empty_input_finishes_after_real_positive_units(tmp_path):
    protected = roots(tmp_path)
    with DiagnosticSort(tmp_path / 'empty', (), protected_roots=protected) as task:
        spool, windows = finish(task, WorkConsumption(sampler=ticking()), {'--cpu-budget-ms': 1})
        assert 0 < len(windows) < 10
        assert delivered(spool, 1) == []


def test_detached_window_report_cannot_replace_the_live_task_state(tmp_path):
    protected = roots(tmp_path)
    with DiagnosticSort(tmp_path / 'spool', diagnostics(3), protected_roots=protected) as task:
        result, report = window(task, WorkConsumption(sampler=unknown), max_units=1)
        result['cursor']['units_completed'] = 999
        result['cursor']['pending_runs'].append({'fake': True})
        result['adaptation']['batch_bytes_after'] = 0
        assert task.state['units_completed'] == 1
        assert task.batch_bytes == 65536
        spool, windows = finish(task, WorkConsumption(sampler=unknown))
        assert delivered(spool, 1) == sorted(diagnostics(3), key=diagnostic_key)


@pytest.mark.parametrize('invalid', [0, -1, True, 1.5])
def test_invalid_window_does_not_change_inputs_or_live_state(tmp_path, invalid):
    protected = roots(tmp_path)
    with DiagnosticSort(tmp_path / 'spool', diagnostics(3), protected_roots=protected) as task:
        before = inventory(tmp_path)
        previous = task.state
        call = WorkConsumption(sampler=unknown).begin()
        with pytest.raises(ValueError):
            advance_spool_sort(task, call, max_units=invalid)
        report = call.finish()
        assert task.state == previous and inventory(tmp_path) == before
        assert report['invocation']['controls']['checks'] == 0


def test_finished_consumption_window_cannot_consume_more_source(tmp_path):
    protected = roots(tmp_path)
    with DiagnosticSort(tmp_path / 'spool', diagnostics(3), protected_roots=protected) as task:
        call = WorkConsumption(sampler=unknown).begin()
        call.finish()
        previous = task.state
        with pytest.raises(ConsumptionError):
            advance_spool_sort(task, call)
        assert task.state == previous


@pytest.mark.parametrize('invalid', [None, {}, 'untrusted'])
def test_only_owned_known_tasks_can_be_advanced(invalid):
    call = WorkConsumption(sampler=unknown).begin()
    with pytest.raises(TypeError):
        advance_spool_sort(invalid, call)
    assert call.finish()['invocation']['controls']['checks'] == 0


@pytest.mark.parametrize('failure', [MemoryError('labelled memory refusal'), OSError(errno.ENOSPC, 'labelled storage refusal')])
def test_real_written_progress_and_recovery_files_survive_failed_minimum_unit(tmp_path, monkeypatch, failure):
    protected = roots(tmp_path)
    (protected[0].root / '.specroad/before-image').write_bytes(b'required original bytes')
    (protected[0].root / '.specroad/checkpoint').write_bytes(b'confirmed checkpoint fixture')
    critical = inventory(protected[0].root)
    with DiagnosticSort(tmp_path / 'spool', diagnostics(21), protected_roots=protected, batch_bytes=1) as task:
        previous = pause_in_merge(task)
        before = inventory(tmp_path / 'spool')
        calls = []
        def refuse(fd, raw):
            calls.append(len(raw))
            raise failure
        monkeypatch.setattr(os, 'write', refuse)
        call = WorkConsumption(sampler=ticking()).begin({'--step-cpu-ms': 1})
        with pytest.raises(type(failure)) as caught:
            advance_spool_sort(task, call)
        report = call.finish()
        assert caught.value is failure and len(calls) == 1
        assert task.state['phase'] == 'failed'
        assert task.state['units_completed'] == previous['units_completed']
        assert inventory(tmp_path / 'spool') == before
        assert report['invocation']['controls']['phases']['spool_unit'] == {'start': 1, 'end': 0}
    assert inventory(protected[0].root) == critical


def test_completed_task_has_no_false_additional_progress_or_batch_change(tmp_path):
    protected = roots(tmp_path)
    with DiagnosticSort(tmp_path / 'spool', diagnostics(2), protected_roots=protected, batch_bytes=2**20) as task:
        spool, windows = finish(task, WorkConsumption(sampler=unknown))
        before = inventory(tmp_path)
        result, report = window(task, WorkConsumption(sampler=ticking()), {'--cpu-budget-ms': 1})
        assert result['state'] == 'completed' and not result['progress_made']
        assert result['units_completed'] == 0 and not result['adaptation']['smallest_unit_attempted']
        assert task.batch_bytes == 2**20 and inventory(tmp_path) == before


@pytest.mark.parametrize('invalid', [0, -1, True, 1.5])
def test_invalid_batch_reduction_keeps_existing_state(tmp_path, invalid):
    protected = roots(tmp_path)
    with DiagnosticSort(tmp_path / 'spool', diagnostics(2), protected_roots=protected) as task:
        before = task.state
        with pytest.raises(ValueError):
            task.reduce_batch_bytes(invalid)
        assert task.state == before and task.batch_bytes == 65536


def test_batch_reduction_is_monotone_and_refuses_a_closed_task(tmp_path):
    protected = roots(tmp_path)
    task = DiagnosticSort(tmp_path / 'spool', diagnostics(2), protected_roots=protected)
    assert task.reduce_batch_bytes(700) == 700
    assert task.reduce_batch_bytes(999999) == 700
    task.close()
    with pytest.raises(ValueError):
        task.reduce_batch_bytes(1)
    assert task.batch_bytes == 700
