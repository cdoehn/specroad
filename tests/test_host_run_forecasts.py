"""Run profiles stay readable as unrelated history grows, without changing dispatch."""
from copy import deepcopy
import json

import pytest

from dev.test_hosts import pool
from dev.test_hosts.config import read_json
from dev.test_hosts.environment import digest
from dev.test_hosts.snapshot import fingerprint, inventory
from verification_support.identity import source_identity
from test_remote_test_hosts import scheduler, scheduler_clock, drain_scheduler


@pytest.mark.parametrize('unrelated', ['test', 'host', 'baseline'])
def test_large_history_still_prepares_a_readable_complete_selected_run(tmp_path, monkeypatch, unrelated):
    root = tmp_path / 'source'
    for name in ('src/specroad', 'tests', 'tools', 'verification'):
        (root / name).mkdir(parents=True)
    (root / 'pyproject.toml').write_text('[project]\nname="synthetic-profile"\n')
    outdir = tmp_path / 'output'; outdir.mkdir()
    hosts = tmp_path / 'hosts.json'
    hosts.write_text(json.dumps({'format_version': 1, 'hosts': [dict(
        name='local', ssh=None, directory=str(tmp_path / 'host'), workers=2)]}))
    env = {'packages': {'pytest-xdist': '3.8.0', 'execnet': '2.1.2'}}
    monkeypatch.setattr(pool, 'environment', lambda: env)
    monkeypatch.setattr(pool, 'available_cpus', lambda: 2)
    monkeypatch.setattr(pool, 'Transport', lambda host: object())
    monkeypatch.setattr(pool, 'check', lambda *a, **kw: dict(hostname='synthetic', account='a' * 64))
    # Keep preparation and serialization real; only external host probes and
    # already selected history rows are inputs to this regression.
    identity = 'tests/test_sample.py::test_known[' + 'x' * 1500 + ']'
    unknown = 'tests/test_sample.py::test_unknown'
    zero = 'tests/test_sample.py::test_zero'
    selected = {'tests/test_sample.py::test_known': identity, unknown: unknown, zero: zero}
    measured = {identity + '\nlocal': 9.5, zero + '\nlocal': 0.0}
    snapshot = {'tests': [dict(test_id=identity, valid=True, duration_ns=2_000_000_000),
                          dict(test_id=unknown, valid=False, duration_ns=8_000_000_000),
                          dict(test_id=zero, valid=True, duration_ns=0)]}
    # One real input-limit crossing per case, without large native projects,
    # database writes, SSH, test subprocesses or fabricated gate outcomes.
    for i in range(11_000):
        other = identity + str(i)
        if unrelated == 'host':
            measured[identity + '\nretired-' + str(i)] = 1.0
        elif unrelated == 'test':
            measured[other + '\nlocal'] = 1.0
        else:
            snapshot['tests'].append(dict(test_id=other, valid=True, duration_ns=1_000_000_000))
    assert len(json.dumps([measured, snapshot]).encode()) > 16_000_000
    original = deepcopy((selected, measured, snapshot))
    def history_inputs(path, environment):
        assert path == root and environment == digest(env)
        return measured
    monkeypatch.setattr(pool, 'estimates', history_inputs)
    profile, path = pool.prepare_pool(root, outdir, hosts, selected, snapshot, 2)
    assert read_json(path) == pool.validate_profile(profile)
    assert profile['selected'] == selected and len(profile['workers']) == 2
    assert profile['estimates'] == {identity + '\nlocal': 9.5, zero + '\nlocal': 0.0}
    assert profile['baseline'] == {identity: 2.0, zero: 0.0}
    assert profile['source_sha256'] == source_identity(root)
    assert profile['snapshot_sha256'] == fingerprint(inventory(root))
    assert (selected, measured, snapshot) == original
    assert path.stat().st_size < 16_000_000


def test_forecast_projection_preserves_all_dispatch_and_host_preferences(monkeypatch):
    clock = scheduler_clock(monkeypatch)
    original = scheduler([90, None, 2, 0, 30, 1], [1.0, 0.5])
    original.profile['baseline']['retired-test'] = 1000.0
    original.profile['estimates'] = {'node0\n0': 65.0, 'node0\n1': 350.0,
        'node2\n1': 0.25, 'node3\n0': 0.0, 'node0\nretired-host': 1.0,
        'retired-test\n0': 1000.0}
    current = scheduler([90, None, 2, 0, 30, 1], [1.0, 0.5])
    snapshot = {'tests': [dict(test_id=k, duration_ns=v * 1e9, valid=True)
                          for k, v in original.profile['baseline'].items()]}
    snapshot['tests'].append(dict(test_id='node1', duration_ns=1_000_000_000, valid=False))
    measured, baseline = pool.run_forecasts(current.profile['selected'],
        current.profile['workers'], original.profile['estimates'], snapshot)
    current.profile.update(estimates=measured, baseline=baseline)
    for old_node, new_node in zip(original.node2pending, current.node2pending):
        for index in range(len(original.collection)):
            assert original.duration(old_node, index) == current.duration(new_node, index)
    before = [(node.gateway.id, index) for node, index in drain_scheduler(original, clock)]
    end = clock[0]
    clock[0] = 0.0
    after = [(node.gateway.id, index) for node, index in drain_scheduler(current, clock)]
    assert after == before and clock[0] == end
    assert sorted(index for _, index in after) == list(range(len(current.collection)))
