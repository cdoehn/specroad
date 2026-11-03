"""Unavailable IPC cannot hide worker exits or substitute saved state for live proof."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
from unittest.mock import Mock

import pytest

from codex_control_tests.external_temp import temporary_directory
from codex_control_tests.worker_observation import wait_stage, WorkerObservationFailure
from specroad_control.errors import ControlError
from specroad_control.local import json_write


class Clock:
    def __init__(self):
        self.now = 0.0

    def read(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def observation():
    with temporary_directory(prefix='wo-') as raw:
        paths = SimpleNamespace(state_file=Path(raw) / 'state.json')
        with tempfile.TemporaryFile(dir=raw) as log:
            yield paths, log, Mock(poll=Mock(return_value=None)), Clock()


def observed(observation, status, seconds=.12):
    paths, log, child, clock = observation
    return wait_stage(paths, child, log, 'retry_wait', seconds,
                      status=status, clock=clock.read, sleep=clock.advance)


def test_transient_unavailable_endpoint_requires_later_live_stage(observation):
    states = [{'state': {'automation': {'stage': 'running'}}},
              {'state': {'automation': {'stage': 'retry_wait'}, 'active_job': False}}]
    status = Mock(side_effect=[ControlError('not_running', 'unavailable'), *states])
    assert observed(observation, status) == states[-1]['state']
    assert status.call_count == 3
    assert observation[3].now == pytest.approx(.06)


@pytest.mark.parametrize('code', [0, 1, -15])
def test_exited_worker_never_passes_from_a_persisted_target_stage(observation, code):
    paths, log, child, clock = observation
    json_write(paths.state_file, {'phase': 'stopped', 'stop_reason': 'low_disk_space',
                                'automation': {'stage': 'retry_wait'}})
    log.write(b'prefix' + b'x' * 17000 + b'worker stopped')
    log.flush()
    offset = log.tell()
    child.poll.return_value = code
    status = Mock()
    with pytest.raises(WorkerObservationFailure) as caught:
        observed(observation, status)
    details = caught.value.details
    assert details['reason'] == 'worker_exited'
    assert details['exit_code'] == code
    assert details['persisted_state']['stop_reason'] == 'low_disk_space'
    assert details['persisted_state']['automation']['stage'] == 'retry_wait'
    assert len(details['log_tail']) == 16384
    assert log.tell() == offset
    status.assert_not_called()
    assert clock.now == 0.0


def test_exit_during_unavailable_status_fails_without_waiting_out_deadline(observation):
    child = observation[2]
    def unavailable(*args):
        child.poll.return_value = 7
        raise ControlError('not_running', 'unavailable')
    with pytest.raises(WorkerObservationFailure) as caught:
        observed(observation, unavailable)
    assert caught.value.details['exit_code'] == 7
    assert caught.value.details['reason'] == 'worker_exited'
    assert observation[3].now == 0.0


def test_exit_during_successful_reply_does_not_accept_stale_live_state(observation):
    def reply(*args):
        observation[2].poll.return_value = 1
        return {'state': {'automation': {'stage': 'retry_wait'}}}
    with pytest.raises(WorkerObservationFailure) as caught:
        observed(observation, reply)
    assert caught.value.details['reason'] == 'worker_exited'
    assert caught.value.details['last_live_state']['automation']['stage'] == 'retry_wait'


def test_continuously_unavailable_live_worker_keeps_the_original_deadline(observation):
    paths, log, child, clock = observation
    json_write(paths.state_file, {'automation': {'stage': 'retry_wait'}})
    status = Mock(side_effect=ControlError('not_running', 'unavailable'))
    with pytest.raises(WorkerObservationFailure) as caught:
        observed(observation, status)
    assert caught.value.details['reason'] == 'deadline_expired'
    assert caught.value.details['exit_code'] is None
    assert caught.value.details['last_live_state'] is None
    assert clock.now == pytest.approx(.12)


def test_security_or_protocol_failure_is_not_retried_as_availability(observation):
    error = ControlError('unsafe_socket', 'unsafe endpoint')
    status = Mock(side_effect=error)
    with pytest.raises(ControlError) as caught:
        observed(observation, status)
    assert caught.value is error
    status.assert_called_once()
    assert observation[3].now == 0.0
