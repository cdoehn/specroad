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


def test_failed_publication_can_be_retried_without_a_new_interval(live_status, monkeypatch):
    pool, node, clock, root, home = live_status
    pool.publish()
    before = (pool.owner.root / 'status.json').read_bytes()
    pool.active['gw0'] = 0
    clock[0] = 10.5

    def fail(*args, **kwargs):
        raise OSError('fixture status failure')

    with monkeypatch.context() as patch:
        patch.setattr(pool.owner, 'publish', fail)
        with pytest.raises(OSError):
            pool.publish()
    assert (pool.owner.root / 'status.json').read_bytes() == before
    pool.publish()
    assert read_status(root, home=home)['hosts']['host']['running'] == 1


def test_final_status_failure_does_not_keep_owner_lock(live_status, monkeypatch):
    pool, node, clock, root, home = live_status
    pool.publish()

    def fail(*args, **kwargs):
        raise OSError('fixture final status failure')

    with monkeypatch.context() as patch:
        patch.setattr(pool.owner, 'publish', fail)
        with pytest.raises(OSError):
            pool.close()
    assert pool.owner.fd is None
    assert not read_status(root, home=home)['active']


def test_final_snapshot_cannot_overwrite_a_replaced_owner_generation(live_status):
    pool, node, clock, root, home = live_status
    pool.publish()
    before = (pool.owner.root / 'status.json').read_bytes()
    (pool.owner.root / 'owner').unlink()
    (pool.owner.root / 'owner').touch(mode=0o600)
    with pytest.raises(ValueError, match='replaced'):
        pool.close()
    assert pool.owner.fd is None
    assert (pool.owner.root / 'status.json').read_bytes() == before


@pytest.mark.parametrize('fault', ['index', 'sequence', 'request'])
def test_throttled_publication_does_not_hide_invalid_permissions(live_status, fault):
    pool, node, clock, root, home = live_status
    pool.publish()
    clock[0] += 0.125
    message = dict(sequence=1, index=0, slot=None)
    if fault == 'index':
        message['index'] = 99
    elif fault == 'sequence':
        message['sequence'] = 2
    else:
        path = pool.owner.root / 'request.json'
        original = path.read_bytes()
        path.write_text('{}')
    try:
        reply = Reply()
        pool.permit(node, reply, message)
        assert reply.replies[-1]['allowed'] is False
        assert pool.errors and pool.ds.shouldstop
        assert not pool.active and not pool.grants
    finally:
        if fault == 'request':
            path.write_bytes(original)


@pytest.mark.parametrize('proxy', [False, True])
def test_fast_native_pool_keeps_complete_history_and_final_status(tmp_path, proxy):
    import json
    from support.live_pool import pool
    from dev.test_hosts.contract import public_proof, verify_pool
    from verification_support.runtime_history import RuntimeHistory

    source = 'def exercise(index):\n    assert 0 <= index < 6\n'
    with pool(tmp_path, proxy=proxy, source=source) as run:
        assert run['process'].wait(timeout=30) == 0, run['log'].read_text()
        observed = json.loads((run['root'] / 'build/observations.json').read_bytes())
        verify_pool(observed, public_proof(run['profile']))
        assert observed['suite_passed'] and observed['tests_run'] == 6
        status = read_status(run['root'], home=run['home'])
        assert not status['active']
        assert status['hosts']['test-host'] == dict(processes=0, running=0, draining=0)
        with RuntimeHistory(run['root']) as history:
            assert history.db.execute('SELECT COUNT(*),COUNT(DISTINCT node),SUM(complete) FROM attempts').fetchone() == (6, 6, 6)
            assert history.db.execute('SELECT COUNT(*) FROM phases').fetchone() == (18,)
            assert history.db.execute('SELECT DISTINCT host FROM attempt_hosts').fetchall() == [('test-host',)]
