"""Exploration eligibility and completion forecasts must admit the same workers."""
import pytest

from test_remote_test_hosts import drain_scheduler, scheduler, scheduler_clock


@pytest.mark.parametrize('count', [1, 2, 188])
def test_host_measurements_cannot_strand_an_unknown_tail_on_idle_workers(monkeypatch, count):
    clock = scheduler_clock(monkeypatch)
    item = scheduler([None] * count, [4, 1])
    fast, slow = item.node2pending
    for identity in item.collection:
        # Unknown to the baseline does not mean unknown to the host history.
        item.profile['estimates'].update({identity + '\n0': 20, identity + '\n1': 1})
    done = drain_scheduler(item, clock)
    assert len(done) == count and all(node is fast for node, _ in done)
    assert not slow.sent


@pytest.mark.parametrize('fast_count', [2, 8])
def test_excluded_fast_slots_cannot_block_early_exploration(monkeypatch, fast_count):
    clock = scheduler_clock(monkeypatch)
    item = scheduler([None] + [100] * fast_count + [1] * 16, [4] * fast_count + [0.5])
    nodes = list(item.node2pending)
    exploration_slots = max(1, (fast_count + 3) // 4)
    for index in range(fast_count + 1):
        item.profile['estimates']['node0\n' + str(index)] = (
            20 - index * 10 if index < exploration_slots else 0.1)
    item.check_schedule()
    chosen = nodes[exploration_slots - 1]
    assert chosen.sent[0] == 0
    assert all(0 not in node.sent for node in nodes if node is not chosen)
    assert all(len(queue) <= 2 for queue in item.node2pending.values())
    assert any(1 <= index <= fast_count for node in nodes[:fast_count] for index in node.sent)
    drain_scheduler(item, clock)


@pytest.mark.parametrize('count', [1, 3])
def test_unknown_tail_uses_measured_finish_times_between_admitted_workers(monkeypatch, count):
    clock = scheduler_clock(monkeypatch)
    item = scheduler([None] * count, [4, 4, 1])
    first, second, slow = item.node2pending
    for identity in item.collection:
        item.profile['estimates'].update({
            identity + '\n0': 20, identity + '\n1': 5, identity + '\n2': 0.1})
    done = drain_scheduler(item, clock)
    assert len(done) == count and all(node is second for node, _ in done)
    assert not first.sent and not slow.sent


def test_known_tests_still_compare_measured_finish_times_across_the_full_pool(monkeypatch):
    clock = scheduler_clock(monkeypatch)
    item = scheduler([100, 100, 100], [4, 1])
    fast, slow = item.node2pending
    for identity in item.collection:
        item.profile['estimates'].update({identity + '\n0': 20, identity + '\n1': 1})
    done = drain_scheduler(item, clock)
    assert len(done) == 3 and all(node is slow for node, _ in done)
    assert not fast.sent
