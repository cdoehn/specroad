"""Decision-local reuse preserves dispatch and never retains cross-event state."""
import pytest

from dev.test_hosts import scheduler as scheduling
from test_remote_test_hosts import scheduler, scheduler_clock, drain_scheduler


class FreshEstimates:
    """The established uncached decision interface, used as a comparison oracle."""

    def __init__(self, item):
        self.available = item.available
        self.duration = item.duration
        self.speed = item.speed

    def assigned(self, node):
        pass


@pytest.mark.parametrize('speeds', [[1, 1], [4, 1, 0.1], [1, 0.5], [2, 2, 2, 0.25]])
def test_reuse_preserves_complete_dispatch_order_and_host_assignments(monkeypatch, speeds):
    clock = scheduler_clock(monkeypatch)
    optimized = scheduling._SchedulingDecision
    outcomes = []
    for decision in (FreshEstimates, optimized):
        clock[0] = 0.0
        monkeypatch.setattr(scheduling, '_SchedulingDecision', decision)
        item = scheduler([None, 200, 100, 80] + [1.0] * 80, speeds)
        done = drain_scheduler(item, clock)
        outcomes.append([(node.gateway.id, index) for node, index in done])
    assert outcomes[0] == outcomes[1]


def test_queue_change_is_visible_during_the_same_dispatch(monkeypatch):
    scheduler_clock(monkeypatch)
    item = scheduler([100, 80, 60, 40, 1, 1], [1, 1])
    item.check_schedule()
    first, second = list(item.node2pending)
    assert first.sent[0] == 0 and second.sent[0] == 1
    assert len(item.node2pending[first]) == len(item.node2pending[second]) == 2
    assert len({index for node in (first, second) for index in node.sent}) == 4


def test_same_dispatch_reuses_estimates_without_losing_queue_updates(monkeypatch):
    clock = scheduler_clock(monkeypatch)
    optimized = scheduling._SchedulingDecision
    results = []
    for decision in (FreshEstimates, optimized):
        clock[0] = 0.0
        monkeypatch.setattr(scheduling, '_SchedulingDecision', decision)
        item = scheduler([100, 80, 60, 40, 1, 1], [1, 1])
        calls = []
        available = item.available

        def observed(node):
            calls.append(node.gateway.id)
            return available(node)

        item.available = observed
        item.check_schedule()
        results.append((len(calls), [list(node.sent) for node in item.node2pending]))
    assert results[0][1] == results[1][1]
    assert results[1][0] < results[0][0]


@pytest.mark.parametrize('change', ['clock', 'host_scale', 'host_measurement'])
def test_new_dispatch_observes_current_inputs_after_a_previous_decision(monkeypatch, change):
    clock = scheduler_clock(monkeypatch)
    optimized = scheduling._SchedulingDecision
    results = []
    for decision in (FreshEstimates, optimized):
        clock[0] = 0.0
        monkeypatch.setattr(scheduling, '_SchedulingDecision', decision)
        item = scheduler([100, 90, 80, 50, 40, 20, 10, 5, 1, None], [2, 1, 0.3])
        item.check_schedule()
        if change == 'clock':
            clock[0] = 1000.0  # all running predictions have overrun
        elif change == 'host_scale':
            item.scale.update({'0': 3.0, '1': 0.1, '2': 2.0})
        else:
            item.profile['estimates'].update({node + '\n1': 0.01 for node in item.collection})
        done = drain_scheduler(item, clock)
        results.append([(node.gateway.id, index) for node, index in done])
    assert results[0] == results[1]


def test_new_worker_gets_fresh_estimates_in_next_dispatch(monkeypatch):
    from test_remote_test_hosts import Node

    clock = scheduler_clock(monkeypatch)
    optimized = scheduling._SchedulingDecision
    results = []
    for decision in (FreshEstimates, optimized):
        clock[0] = 0.0
        monkeypatch.setattr(scheduling, '_SchedulingDecision', decision)
        item = scheduler([200, 100, 80] + [1] * 80, [1, 0.5])
        item.check_schedule()
        additional = Node('gw2')
        item.node2pending[additional] = []
        item.profile['workers']['gw2'] = dict(host='extra', speed=4)
        done = drain_scheduler(item, clock)
        assert additional.sent
        results.append([(node.gateway.id, index) for node, index in done])
    assert results[0] == results[1]
