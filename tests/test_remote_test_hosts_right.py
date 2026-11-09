"""Reject malformed host evidence and preserve real start/phase/slot boundaries."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from dev.test_hosts.config import host, load
from dev.test_hosts.environment import environment, digest, account
from dev.test_hosts.history import HistoryClient, HistoryServer
from dev.test_hosts.lease import Lease
from dev.test_hosts.pool import public_proof, validate_profile, verify_pool
from dev.test_hosts.snapshot import copy_snapshot, inventory
from dev.test_hosts.ssh import Transport
from verification_support.runtime_history import RuntimeHistory
from test_remote_test_hosts import configured, Reply, scheduler


def profile():
    env = environment()
    resources = dict(format_version=1, available_cpus=4, workers=1, worker_limit=1, nested=False, nice_minimum=10)
    row = dict(host='sample', hostname='sample', account='d' * 64, root='/tmp/synthetic-source',
        environment_sha256=digest(env), resources=resources, speed=1.0, spec='popen', budget=1, remote=False)
    return dict(format_version=1, source_sha256='a' * 64, snapshot_sha256='b' * 64,
        environment=env, workers={'gw0': row}, proxies=[], selected={'tests/test_x.py::test_a': 'case'}, estimates={}, baseline={'case': 1.0})


@pytest.mark.parametrize('change', [
    {'ssh': '-oProxyCommand=bad'}, {'ssh': 'name//python=bad'}, {'directory': '/tmp/../elsewhere'},
    {'directory': '/'}, {'workers': 0}, {'workers': True}, {'speed': float('nan')}, {'persist': -1},
    {'session_id': 'forbidden-field'}, {'directory': '/tmp/with spaces'},
])
def test_host_configuration_rejects_unsafe_or_ambiguous_values(change):
    with pytest.raises((ValueError, TypeError)):
        configured(**change)


@pytest.mark.parametrize('fault', ['version', 'worker-gap', 'budget', 'source', 'duplicate-test', 'negative-time', 'nan-speed', 'mixed-host', 'extra'])
def test_profile_contract_cannot_hide_unbound_workers_or_tests(fault):
    value = profile()
    if fault == 'version': value['format_version'] = True
    elif fault == 'worker-gap': value['workers']['gw2'] = value['workers'].pop('gw0')
    elif fault == 'budget': value['workers']['gw0']['budget'] = 0
    elif fault == 'source': value['source_sha256'] = 'wrong'
    elif fault == 'duplicate-test': value['selected']['tests/test_x.py::test_b'] = 'case'
    elif fault == 'negative-time': value['baseline']['case'] = -1
    elif fault == 'nan-speed': value['workers']['gw0']['speed'] = float('nan')
    elif fault == 'mixed-host': value['workers']['gw1'] = deepcopy(value['workers']['gw0'])
    else: value['credentials'] = {}
    with pytest.raises(ValueError):
        validate_profile(value)


@pytest.mark.parametrize('fault', ['source', 'host', 'slot', 'priority', 'missing', 'environment', 'rpc-error'])
def test_gate_rejects_incomplete_or_foreign_host_proofs(fault):
    value = profile(); binding = public_proof(value); row = value['workers']['gw0']
    output = dict(host='sample', hostname='sample', account='d' * 64, environment_sha256=row['environment_sha256'],
        source_sha256='a' * 64, snapshot_sha256='b' * 64, slot=0,
        resources={**row['resources'], 'nice_actual': 10}, io_priority={'class': 2, 'priority': 7})
    observation = dict(workers=['gw0'], host_pool=dict(binding=binding, workers={'gw0': output}, errors=[]))
    verify_pool(observation, binding)
    if fault == 'source': output['source_sha256'] = 'c' * 64
    elif fault == 'host': output['host'] = 'other'
    elif fault == 'slot': output['slot'] = True
    elif fault == 'priority': output['resources']['nice_actual'] = 0
    elif fault == 'missing': observation['host_pool']['workers'] = {}
    elif fault == 'environment': output['environment_sha256'] = 'c' * 64
    else: observation['host_pool']['errors'] = ['unacknowledged']
    with pytest.raises(ValueError): verify_pool(observation, binding)


@pytest.mark.parametrize('fault', ['sequence', 'foreign-worker', 'foreign-id', 'phase', 'duration', 'subtest'])
def test_bad_rpc_cannot_ack_or_complete_a_native_attempt(tmp_path, fault):
    channel = Reply()
    with RuntimeHistory(tmp_path) as store:
        run = store.begin('a' * 64, 1)
    server = HistoryServer(channel, tmp_path, run, 'gw0', 'host', 'b' * 64, {'node': 'case'})
    try:
        server.receive((1, 'start', ['node', 'case', 'gw0']))
        sequence, values = 2, ['node', 'case', 'gw0', 'setup', 1.0, 'passed', False]
        if fault == 'sequence': sequence = 1
        elif fault == 'foreign-worker': values[2] = 'gw1'
        elif fault == 'foreign-id': values[1] = 'another'
        elif fault == 'phase': values[3] = 'invented'
        elif fault == 'duration': values[4] = float('inf')
        else: values[6] = 'False'
        server.receive((sequence, 'phase', values))
        assert channel.replies[-1][1] == 'rejected' and server.errors
        with RuntimeHistory(tmp_path) as store:
            assert store.snapshot(['case'])['tests'][0]['duration_ns'] is None
            assert store.db.execute('SELECT COUNT(*) FROM phases').fetchone() == (0,)
    finally:
        server.receive(None)


def test_rpc_database_write_failure_is_not_acknowledged(tmp_path):
    import sqlite3
    channel = Reply()
    with RuntimeHistory(tmp_path) as store:
        run = store.begin('a' * 64, 1)
    server = HistoryServer(channel, tmp_path, run, 'gw0', 'host', 'b' * 64, {'node': 'case'})
    try:
        server.receive((1, 'start', ['node', 'case', 'gw0']))
        server.history.db.set_authorizer(lambda action, table, *rest: sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_INSERT and table == 'phases' else sqlite3.SQLITE_OK)
        server.receive((2, 'phase', ['node', 'case', 'gw0', 'setup', 1.0, 'passed', False]))
        assert channel.replies[-1] == (1, 'rejected')
    finally:
        server.receive(None)


def test_missing_ack_stops_worker_before_test_body():
    class Broken:
        def send(self, value): pass
        def receive(self, timeout): raise EOFError('connection lost')
    with pytest.raises(EOFError):
        HistoryClient(Broken()).start(1, 'node', 'case', 'gw0')


def test_large_remote_manifest_is_streamed_without_oversized_argv(tmp_path):
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs)); return SimpleNamespace(returncode=0, stdout='true')
    script = '# source manifest\n' + ('#' + 'x' * 300000) + '\nprint(True)\n'
    assert Transport(configured(), runner=run, state=tmp_path).python(script) is True
    assert max(map(len, calls[0][0])) < 4096 and calls[0][1]['input'] == script


def test_symlinked_snapshot_never_copies_outside_bytes(tmp_path):
    root = tmp_path / 'root'; (root / 'tools').mkdir(parents=True)
    outside = tmp_path / 'secret'; outside.write_text('synthetic secret')
    (root / 'tools/input.py').symlink_to(outside)
    with pytest.raises(ValueError): copy_snapshot(root, tmp_path / 'copy')
    assert not (tmp_path / 'copy').exists()


def test_lease_releases_after_real_worker_process_death(tmp_path):
    directory = tmp_path / 'slots'
    tools = Path(__file__).resolve().parents[1] / 'tools'
    program = ('import sys; sys.path.insert(0,sys.argv[1]); from dev.test_hosts.lease import Lease; '
               'lease=Lease(1,directory=sys.argv[2]); print("ready",flush=True); sys.stdin.read()')
    child = subprocess.Popen([sys.executable, '-I', '-B', '-c', program, str(tools), str(directory)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == 'ready'
        with pytest.raises(ValueError, match='occupied'): Lease(1, directory=directory)
        child.kill(); child.communicate(timeout=10)
        lease = Lease(1, directory=directory); lease.close()
    finally:
        if child.poll() is None: child.kill()
        child.communicate(timeout=10)


def test_weak_host_does_not_receive_long_tail_just_to_fill_nextitem():
    item = scheduler([1000, 990, 500, 400, 1], [10, 0.1])
    item.check_schedule()
    slow = list(item.node2pending)[1]
    assert slow.sent == [4] and slow.shutting_down
    assert item.pending == [2, 3]


def test_online_speed_observation_changes_future_unknown_host_ranking():
    item = scheduler([None, None, 100, 90, 80, 1], [2, 1])
    item.scale['0'] = 4
    item.check_schedule()
    fast = list(item.node2pending)[1]
    assert any(i in fast.sent for i in (0, 1))


def test_monitor_reads_old_database_without_inventing_host_identity(tmp_path):
    from dev.status.monitor_data import history
    with RuntimeHistory(tmp_path) as store:
        run = store.begin('a' * 64, 1); store.start(run, 'node', 'case', 'gw0')
        store.db.execute('DROP TABLE attempt_hosts'); store.db.commit()
        path = store.path
    rows = history(path)
    assert rows[0]['host'] is None and rows[0]['environment_sha256'] is None
