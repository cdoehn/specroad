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
