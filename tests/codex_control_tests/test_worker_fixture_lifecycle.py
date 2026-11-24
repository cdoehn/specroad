"""Bounded fixture observation and cleanup; the real worker tests remain mandatory."""
import io
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from specroad_control.errors import ControlError
from codex_control_tests import test_deferred_handover as deferred


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def protocol_error(cause):
    # Match the native IPC boundary, including the suppressed but retained cause.
    try:
        raise cause
    except (TimeoutError, ValueError):
        try:
            raise ControlError('protocol_error', 'Synthetic IPC failure') from None
        except ControlError as error:
            return error


@pytest.fixture
def observer(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(deferred, 'time', clock)
    case = deferred.DeferredCase('runTest')
    case.paths = SimpleNamespace()
    case.child = Mock()
    case.child.poll.return_value = None
    case.worker_log = io.BytesIO(b'synthetic worker log')
    return case, clock


@pytest.mark.parametrize('initial', ['not_running', 'timeout'])
def test_observation_waits_for_valid_state_after_transient_status_failure(observer, monkeypatch, initial):
    case, _clock = observer
    error = (ControlError('not_running', 'Starting') if initial == 'not_running'
             else protocol_error(TimeoutError()))
    ready = {'automation': {'stage': 'apply_reconciliation_waiting'}}
    request = Mock(side_effect=[error, {'state': {'automation': {'stage': 'initializing'}}}, {'state': ready}])
    monkeypatch.setattr(deferred, 'request', request)
    result = case.await_state(lambda state: state['automation']['stage'] == 'apply_reconciliation_waiting')
    assert result is ready
    assert request.call_args_list == [call(case.paths, 'status')] * 3


def test_repeated_status_timeouts_do_not_extend_the_overall_deadline(observer, monkeypatch):
    case, clock = observer
    attempts = []

    def timeout(paths, command):
        attempts.append((paths, command))
        clock.now += 1.0
        raise protocol_error(TimeoutError())

    monkeypatch.setattr(deferred, 'request', timeout)
    with pytest.raises(AssertionError, match='did not reach expected state'):
        case.await_state(lambda state: True, timeout=3)
    assert 3 <= clock.now < 4
    assert 2 <= len(attempts) <= 3
    assert all(paths is case.paths and command == 'status' for paths, command in attempts)


@pytest.mark.parametrize('kind', ['malformed', 'missing_boolean', 'unsafe_socket', 'wrong_scope'])
def test_invalid_or_unsafe_status_is_not_retried(observer, monkeypatch, kind):
    case, _clock = observer
    error = (protocol_error(ValueError('malformed reply')) if kind == 'malformed'
             else ControlError('protocol_error' if kind == 'missing_boolean' else kind, 'Rejected'))
    request = Mock(side_effect=error)
    monkeypatch.setattr(deferred, 'request', request)
    with pytest.raises(ControlError) as caught:
        case.await_state(lambda state: True)
    assert caught.value is error
    request.assert_called_once_with(case.paths, 'status')


def test_dead_worker_is_not_accepted_as_a_transient_status_failure(observer, monkeypatch):
    case, _clock = observer
    case.child.poll.return_value = 1
    request = Mock()
    monkeypatch.setattr(deferred, 'request', request)
    with pytest.raises(AssertionError, match='Isolated worker stopped'):
        case.await_state(lambda state: True)
    request.assert_not_called()


def test_cleanup_reaps_hung_child_and_preserves_shutdown_failure():
    child = Mock()
    child.poll.return_value = None
    failure = deferred.subprocess.TimeoutExpired(['synthetic-worker'], 20)
    child.wait.side_effect = [failure, -9]
    with pytest.raises(deferred.subprocess.TimeoutExpired) as caught:
        deferred.stop_test_worker(child)
    assert caught.value is failure
    assert child.mock_calls == [call.poll(), call.terminate(), call.wait(timeout=20),
                               call.kill(), call.wait(timeout=5)]


@pytest.mark.parametrize('already_exited', [False, True])
def test_cleanup_never_kills_a_normally_stopped_child(already_exited):
    child = Mock()
    child.poll.return_value = 0 if already_exited else None
    child.wait.return_value = 0
    deferred.stop_test_worker(child)
    child.kill.assert_not_called()
    if already_exited:
        child.terminate.assert_not_called()
        child.wait.assert_not_called()
    else:
        child.terminate.assert_called_once_with()
        child.wait.assert_called_once_with(timeout=20)
