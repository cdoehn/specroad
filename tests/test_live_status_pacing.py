"""A paced external snapshot never delays the authoritative test controls."""
from types import SimpleNamespace

import pytest

from dev.test_control.store import Owner, change, read_status
from dev.test_hosts.live import LivePool
from test_remote_test_hosts import Node, Reply


@pytest.fixture
def live_status(tmp_path, monkeypatch):
    clock = [10.0]
    monkeypatch.setattr('dev.test_hosts.live.time', SimpleNamespace(monotonic=lambda: clock[0]))
    root, home = tmp_path / 'apply', tmp_path / 'state'
    pool = LivePool(SimpleNamespace(_sr_host_profile=dict(format_version=2,
        workers={'gw0': dict(host='host', budget=1)})))
    pool.owner = Owner(root, {'host': 1}, {'host': 1}, home=home)
    node = Node('gw0')
    sched = SimpleNamespace(collection=['a', 'b'], node2pending={node: [0, 1]},
        reclaimed={}, has_pending=False, denies_reclaimed=lambda *args: False)
    pool.ds = SimpleNamespace(sched=sched, _active_nodes={node}, shuttingdown=False, shouldstop=False)
    try:
        yield pool, node, clock, root, home
    finally:
        pool.close()


def test_status_coalesces_events_and_publishes_latest_snapshot(live_status):
    pool, node, clock, root, home = live_status
    pool.publish()
    path = pool.owner.root / 'status.json'
    original = path.read_bytes()
    inode = path.stat().st_ino
    pool.active['gw0'] = 0
    clock[0] += 0.25
    pool.publish()
    assert path.read_bytes() == original and path.stat().st_ino == inode
    clock[0] += 0.25
    pool.publish()
    status = read_status(root, home=home)
    assert status['active'] and status['hosts']['host'] == dict(processes=1, running=1, draining=0)


def test_pause_denies_next_permission_before_next_status_publication(live_status):
    pool, node, clock, root, home = live_status
    pool.publish()
    change(root, pool.owner.run, {'host': 0}, home=home)
    clock[0] += 0.125
    reply = Reply()
    pool.permit(node, reply, dict(sequence=1, index=0, slot=None))
    assert reply.replies == [dict(sequence=1, allowed=False)]
    assert pool.owner.desired == {'host': 0} and node.shutting_down
    assert not pool.active and not pool.grants and not pool.errors
    # Display freshness is not the authority for the decision above.
    assert read_status(root, home=home)['desired'] == {'host': 1}
    clock[0] = 10.5
    pool.publish()
    assert read_status(root, home=home)['desired'] == {'host': 0}


def test_close_flushes_final_snapshot_and_releases_owner(live_status):
    pool, node, clock, root, home = live_status
    pool.publish()
    pool.ds._active_nodes.clear()
    clock[0] += 0.125
    pool.close()
    status = read_status(root, home=home)
    assert not status['active']
    assert status['hosts']['host'] == dict(processes=0, running=0, draining=0)
    before = (pool.owner.root / 'status.json').read_bytes()
    pool.close()
    assert (pool.owner.root / 'status.json').read_bytes() == before
