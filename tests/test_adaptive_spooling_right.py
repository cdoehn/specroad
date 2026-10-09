"""Observed minimum-step failures, retained files and finite complete work."""

import errno
import json
import os

import pytest

from specroad.diagnostics import diagnostic_key
from specroad.diagnostics.spooling import DiagnosticSort
from specroad.graph.path_output import PathSort
from specroad.runtime.adaptive_spooling import advance_spool_sort_outcome
from specroad.runtime.consumption import ConsumptionError, WorkConsumption
from specroad.security.errors import SafetyViolation
from support.processes import run_core
from support.read_only import inventory
from test_adaptive_spooling_work import ticking, unknown
from test_spooling_right import roots, diagnostics, delivered, layered_paths, pause_in_merge


def outcome(task, ledger=None, options=None, *, max_units=256):
    call = (ledger or WorkConsumption(sampler=unknown)).begin(options)
    try:
        return advance_spool_sort_outcome(task, call, max_units=max_units)
    finally:
        call.finish()


def finish(task, ledger=None, options=None, *, max_units=256):
    ledger = ledger or WorkConsumption(sampler=unknown)
    for _ in range(10000):
        previous = task.state['units_completed']
        value = outcome(task, ledger, options, max_units=max_units)
        assert value['blocker'] is None
        assert value['window']['progress_made']
        assert 0 < value['window']['units_completed'] <= max_units
        assert task.state['units_completed'] > previous
        assert not value['window']['durable_checkpoint']
        if value['state'] == 'completed':
            assert value['exit_code'] == 0
            return task.result
        assert value['state'] == 'active' and value['exit_code'] is None
    raise AssertionError('Finite work failed to finish with positive progress')


@pytest.mark.parametrize('flag', ['--cpu-budget-ms', '--wall-budget-ms', '--step-cpu-ms', '--step-wall-ms'])
def test_tiny_target_finishes_all_records_without_empty_windows_or_false_blockers(tmp_path, flag):
    protected = roots(tmp_path)
    before = inventory(protected[0].root)
    consumed = []
    def source():
        for index, record in enumerate(diagnostics(31)):
            consumed.append(index)
            yield record
    with DiagnosticSort(tmp_path / 'spool', source(), protected_roots=protected, batch_bytes=2**20) as task:
        spool = finish(task, WorkConsumption(sampler=ticking()), {flag: 1}, max_units=1000)
        assert task.batch_bytes == 1 and spool.manifest['batch']['peak_records'] == 1
        assert delivered(spool, 3) == sorted(diagnostics(31), key=diagnostic_key)
        assert consumed == list(range(31))
    assert inventory(protected[0].root) == before


@pytest.mark.parametrize('units', [1, 7, 1000])
def test_unknown_capacity_does_not_prevent_complete_bounded_work(tmp_path, units):
    with DiagnosticSort(tmp_path / 'spool', diagnostics(19), protected_roots=roots(tmp_path)) as task:
        spool = finish(task, max_units=units)
        assert delivered(spool, 2) == sorted(diagnostics(19), key=diagnostic_key)


def test_conservative_prepared_path_work_preserves_all_ordered_paths(tmp_path):
    paths, _ = layered_paths(3)
    expected = paths[3:] + list(reversed(paths))
    with PathSort(tmp_path / 'spool', iter(expected), protected_roots=roots(tmp_path)) as task:
        spool = finish(task, WorkConsumption(sampler=ticking()), {'--step-wall-ms': 1})
        assert delivered(spool, 1) == expected


_REFUSALS = [
    (errno.EACCES, 'access_denied', 'restore_guarded_spool_and_source_permissions'),
    (errno.EPERM, 'access_denied', 'restore_guarded_spool_and_source_permissions'),
    (errno.ENOENT, 'bound_path_missing', 'restore_bound_inputs_and_spool_paths_then_revalidate'),
    (errno.EMFILE, 'descriptor_unavailable', 'make_a_file_descriptor_available'),
    (errno.ENFILE, 'descriptor_unavailable', 'make_a_file_descriptor_available'),
    (errno.ENOMEM, 'memory_unavailable', 'make_memory_for_the_failed_step_available'),
    (errno.ENOSPC, 'storage_unavailable', 'make_space_available_without_deleting_recovery_data'),
    (errno.EFBIG, 'file_size_limit', 'provide_a_file_size_limit_that_allows_the_required_spool'),
    (errno.EROFS, 'read_only_storage', 'provide_writable_external_spool_storage'),
    (errno.EIO, 'io_failure', 'restore_reliable_source_and_spool_io'),
    (errno.ENOSYS, 'safe_io_unavailable', 'provide_supported_guarded_file_io'),
    (None, 'memory_unavailable', 'make_memory_for_the_failed_step_available'),
]
if hasattr(errno, 'EDQUOT'):
    _REFUSALS.append((errno.EDQUOT, 'storage_unavailable', 'make_space_available_without_deleting_recovery_data'))


@pytest.mark.parametrize('code,reason,action', _REFUSALS)
def test_observed_failed_merge_reports_cause_attempts_retained_progress_and_remedy(tmp_path, monkeypatch, code, reason, action):
    protected = roots(tmp_path)
    for name in ('before-image', 'checkpoint', 'snapshot'):
        (protected[0].root / '.specroad' / name).write_bytes(b'critical recovery bytes')
    critical = inventory(protected[0].root)
    with DiagnosticSort(tmp_path / 'spool', diagnostics(27), protected_roots=protected, batch_bytes=700) as task:
        previous = pause_in_merge(task)
        before = inventory(tmp_path / 'spool')
        writes = []
        failure = MemoryError('labelled refusal') if code is None else OSError(code, 'labelled refusal')
        def refuse(descriptor, data):
            writes.append(len(data))
            raise failure
        monkeypatch.setattr(os, 'write', refuse)
        call = WorkConsumption(sampler=ticking()).begin({'--step-cpu-ms': 1})
        value = advance_spool_sort_outcome(task, call)
        report = call.finish()
        assert value['state'] == 'blocked' and value['exit_code'] == 5 and value['window'] is None
        blocker = value['blocker']
        assert blocker['blocked_reason'] == reason and blocker['required_action'] == action
        assert blocker['native_errno'] == code and not blocker['minimum_resources_known']
        alternatives = blocker['alternatives']
        assert alternatives['batch_bytes_before'] == 700 and alternatives['batch_bytes_after'] == 1
        assert alternatives['smallest_unit_attempted'] and not alternatives['automatic_retry_performed']
        retained = blocker['retained_progress']
        assert retained['observed_cursor']['units_completed'] == previous['units_completed'] > 0
        assert retained['units_completed_in_window'] == 0
        assert retained['observed_cursor']['operation']['output']['name'] == previous['operation']['output']['name']
        assert not retained['live_task_resumable'] and not retained['buffered_input_resumable']
        assert not retained['durable_checkpoint'] and retained['checkpoint'] is None
        assert not retained['external_spool_files_deleted'] and not blocker['critical_data_deleted']
        assert not blocker['project_writes_performed'] and len(writes) == 1
        assert report['invocation']['controls']['phases']['spool_unit'] == {'start': 1, 'end': 0}
        assert inventory(tmp_path / 'spool') == before
        assert task._closed and not task._spool._fds
        with pytest.raises(ValueError):
            outcome(task)
        assert len(writes) == 1
        retained['observed_cursor']['units_completed'] = -1
        assert task.state['units_completed'] == previous['units_completed']
    assert inventory(protected[0].root) == critical


def test_real_short_write_prefix_survives_later_refusal_without_claiming_completed_unit(tmp_path, monkeypatch):
    protected = roots(tmp_path)
    critical = inventory(protected[0].root)
    with DiagnosticSort(tmp_path / 'spool', diagnostics(21), protected_roots=protected, batch_bytes=1) as task:
        previous = pause_in_merge(task)
        name = previous['operation']['output']['name']
        target = tmp_path / 'spool' / name
        before = target.read_bytes()
        original = os.write
        writes = []
        def partially_write(descriptor, data):
            if not writes:
                prefix = bytes(data[:7])
                writes.append(prefix)
                return original(descriptor, prefix)
            raise OSError(errno.ENOSPC, 'labelled failure after real write')
        monkeypatch.setattr(os, 'write', partially_write)
        value = outcome(task)
        assert value['state'] == 'blocked'
        retained = value['blocker']['retained_progress']
        assert retained['units_completed_in_window'] == 0
        assert retained['observed_cursor']['operation']['output']['records_written'] == previous['operation']['output']['records_written']
        assert not retained['observed_cursor']['operation']['output']['sealed']
        assert target.read_bytes() == before + writes[0]
        assert not retained['live_task_resumable'] and value['window'] is None
    assert inventory(protected[0].root) == critical


@pytest.mark.parametrize('failure', [ValueError('input'), RuntimeError('bug'), OSError(errno.EBADF, 'descriptor bug'), KeyboardInterrupt()],
                         ids=['input', 'programming', 'unknown_errno', 'interrupt'])
def test_unexpected_failures_propagate_without_becoming_resource_claims(tmp_path, monkeypatch, failure):
    with DiagnosticSort(tmp_path / 'spool', diagnostics(19), protected_roots=roots(tmp_path), batch_bytes=1) as task:
        pause_in_merge(task)
        before = inventory(tmp_path / 'spool')
        def refuse(*unused):
            raise failure
        monkeypatch.setattr(os, 'write', refuse)
        with pytest.raises(type(failure)) as caught:
            outcome(task)
        assert caught.value is failure and inventory(tmp_path / 'spool') == before


@pytest.mark.parametrize('invalid', [0, -1, True, 1.5])
def test_invalid_window_cannot_even_reduce_the_future_batch_target(tmp_path, invalid):
    with DiagnosticSort(tmp_path / 'spool', diagnostics(3), protected_roots=roots(tmp_path)) as task:
        previous = task.state
        before = inventory(tmp_path)
        with pytest.raises(ValueError):
            outcome(task, max_units=invalid)
        assert task.state == previous and task.batch_bytes == 65536
        assert inventory(tmp_path) == before


@pytest.mark.parametrize('invalid', [None, {}, 'foreign'])
def test_unowned_tasks_are_not_used_as_a_source_of_blocker_claims(invalid):
    with pytest.raises(TypeError):
        outcome(invalid)


def test_finished_measurement_window_cannot_reduce_or_advance_a_task(tmp_path):
    with DiagnosticSort(tmp_path / 'spool', diagnostics(3), protected_roots=roots(tmp_path)) as task:
        call = WorkConsumption(sampler=unknown).begin()
        call.finish()
        previous = task.state
        with pytest.raises(ConsumptionError):
            advance_spool_sort_outcome(task, call)
        assert task.state == previous and task.batch_bytes == 65536


@pytest.mark.parametrize('edge', ['start', 'end'])
@pytest.mark.parametrize('failure', [MemoryError('observer'), OSError(errno.EIO, 'observer')])
def test_observer_failure_is_not_misreported_as_a_failed_spool_step(tmp_path, monkeypatch, edge, failure):
    with DiagnosticSort(tmp_path / 'spool', diagnostics(3), protected_roots=roots(tmp_path)) as task:
        call = WorkConsumption(sampler=unknown).begin()
        original = call.control
        def observe(point):
            if point.edge == edge:
                raise failure
            return original(point)
        monkeypatch.setattr(call, 'control', observe)
        with pytest.raises(type(failure)) as caught:
            advance_spool_sort_outcome(task, call)
        call.finish()
        assert caught.value is failure and not task._closed
        assert task.state['units_completed'] == (0 if edge == 'start' else 1)
        spool = finish(task)
        assert delivered(spool, 1) == sorted(diagnostics(3), key=diagnostic_key)


def test_changed_spool_permissions_remain_a_safety_violation(tmp_path):
    protected = roots(tmp_path)
    with DiagnosticSort(tmp_path / 'spool', diagnostics(3), protected_roots=protected) as task:
        (tmp_path / 'spool').chmod(0o777)
        try:
            with pytest.raises(SafetyViolation):
                outcome(task)
        finally:
            (tmp_path / 'spool').chmod(0o700)


def test_failed_prefetched_input_is_not_advertised_as_resumable_memory(tmp_path, monkeypatch):
    with DiagnosticSort(tmp_path / 'spool', diagnostics(25), protected_roots=roots(tmp_path), batch_bytes=700) as task:
        for _ in range(100):
            previous = task.advance(1)
            if previous['pending_input_sequence'] is not None:
                break
        assert previous['buffered_records'] > 0
        assert previous['pending_input_sequence'] == previous['accepted_records']
        before = inventory(tmp_path / 'spool')
        def refuse(*unused):
            raise MemoryError('labelled buffered write refusal')
        monkeypatch.setattr(os, 'write', refuse)
        value = outcome(task)
        blocker = value['blocker']
        assert blocker['alternatives']['buffered_records_before'] == previous['buffered_records']
        assert blocker['alternatives']['pending_input_sequence_before'] == previous['pending_input_sequence']
        assert not blocker['retained_progress']['buffered_input_resumable']
        assert blocker['next_action'] == 'after_remedy_revalidate_source_and_start_new_task_in_new_spool'
        assert inventory(tmp_path / 'spool') == before


def test_source_failure_after_real_progress_has_no_partial_success_result(tmp_path):
    pulled = []
    def source():
        for record in diagnostics(2):
            pulled.append(record)
            yield record
        raise MemoryError('labelled source refusal')
    with DiagnosticSort(tmp_path / 'spool', source(), protected_roots=roots(tmp_path)) as task:
        value = outcome(task, max_units=1000)
        assert value['state'] == 'blocked' and value['window'] is None
        retained = value['blocker']['retained_progress']
        assert retained['units_completed_in_window'] > 0
        assert retained['observed_cursor']['accepted_records'] == 2 and len(pulled) == 2
        with pytest.raises(ValueError):
            _ = task.result
        before = inventory(tmp_path / 'spool')
        with pytest.raises(ValueError):
            outcome(task)
        assert len(pulled) == 2 and inventory(tmp_path / 'spool') == before


def test_already_completed_task_returns_complete_without_new_work(tmp_path):
    with DiagnosticSort(tmp_path / 'spool', diagnostics(3), protected_roots=roots(tmp_path)) as task:
        finish(task)
        before = inventory(tmp_path)
        value = outcome(task)
        assert value['state'] == 'completed' and value['exit_code'] == 0 and value['blocker'] is None
        assert value['window']['units_completed'] == 0 and not value['window']['progress_made']
        assert inventory(tmp_path) == before


_NATIVE = '''
import errno, json, os, resource, signal
from pathlib import Path
from specroad.diagnostics import Diagnostic
from specroad.diagnostics.spooling import DiagnosticSort
from specroad.runtime.adaptive_spooling import advance_spool_sort_outcome
from specroad.runtime.consumption import CounterSample, WorkConsumption
from specroad.security.paths import ProjectBoundary
project = Path('project').resolve()
project.mkdir()
(project / 'critical').write_bytes(b'recovery fixture')
task = DiagnosticSort(Path('spool').resolve(), [Diagnostic('D', 'info', 'fixture', 'finding')],
                      protected_roots=(ProjectBoundary(project),), batch_bytes=1)
task.advance(1)
call = WorkConsumption(sampler=lambda: CounterSample(None, None, None)).begin()
'''


@pytest.mark.parametrize('limit,code,reason', [('RLIMIT_NOFILE', errno.EMFILE, 'descriptor_unavailable'),
                                            ('RLIMIT_FSIZE', errno.EFBIG, 'file_size_limit')])
def test_real_native_limit_refuses_minimum_file_operation_without_deleting_critical_data(tmp_path, limit, code, reason):
    body = _NATIVE + 'limit = resource.' + limit + '\n' + '''
previous = resource.getrlimit(limit)
handler = signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
try:
    resource.setrlimit(limit, (0, previous[1]))
    value = advance_spool_sort_outcome(task, call)
finally:
    resource.setrlimit(limit, previous)
    signal.signal(signal.SIGXFSZ, handler)
call.finish()
assert task._closed and not task._spool._fds
assert (project / 'critical').read_bytes() == b'recovery fixture'
print(json.dumps(value))
'''
    completed = run_core(body, tmp_path, capture=True)
    assert completed.returncode == 0, completed.stderr
    value = json.loads(completed.stdout)
    assert value['state'] == 'blocked' and value['exit_code'] == 5 and value['window'] is None
    blocker = value['blocker']
    assert blocker['native_errno'] == code and blocker['blocked_reason'] == reason
    assert blocker['alternatives']['smallest_unit_attempted']
    assert blocker['retained_progress']['observed_cursor']['accepted_records'] == 1
    assert blocker['retained_progress']['units_completed_in_window'] == 0
    assert (tmp_path / 'project/critical').read_bytes() == b'recovery fixture'


def test_actual_allocation_refusal_in_labelled_initializer_reports_unknown_minimum(tmp_path):
    body = _NATIVE + '''
from specroad.diagnostics import spooling
observed = []
def refused():
    # Native refusal in a labelled stand-in, not a claim that hashing a spool
    # requires one TiB or that this measures the real minimum memory demand.
    previous = resource.getrlimit(resource.RLIMIT_AS)
    try:
        resource.setrlimit(resource.RLIMIT_AS, (0, previous[1]))
        bytearray(1 << 40)
    except MemoryError:
        observed.append('native_allocation_refused')
        raise
    finally:
        resource.setrlimit(resource.RLIMIT_AS, previous)
spooling.sha256 = refused
value = advance_spool_sort_outcome(task, call)
call.finish()
assert observed == ['native_allocation_refused']
assert task._closed and not task._spool._fds
print(json.dumps(value))
'''
    completed = run_core(body, tmp_path, capture=True)
    assert completed.returncode == 0, completed.stderr
    value = json.loads(completed.stdout)
    assert value['state'] == 'blocked' and value['window'] is None
    assert value['blocker']['blocked_reason'] == 'memory_unavailable'
    assert value['blocker']['native_errno'] is None and not value['blocker']['minimum_resources_known']
    assert (tmp_path / 'project/critical').read_bytes() == b'recovery fixture'
