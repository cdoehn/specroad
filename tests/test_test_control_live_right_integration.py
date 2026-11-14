"""Native multi-Apply leases and unchanged fail-closed worker-loss behavior."""
import json

import pytest

from support.live_pool import pool, await_value
from dev.test_control.store import read_status, change
from dev.test_hosts.contract import public_proof, verify_pool
from dev.test_hosts.environment import digest
from verification_support.runtime_history import RuntimeHistory


def test_two_native_applies_share_atomic_slots_but_keep_distinct_measurements(tmp_path):
    state = tmp_path/'shared-state'
    with pool(tmp_path/'one', initial=1, state=state) as first, pool(tmp_path/'two', initial=1, state=state) as second:
        for p in (first, second):
            await_value(lambda: read_status(p['root'], home=p['home']), p['process'], p['log'])
        await_value(lambda: list((first['target']/'build').glob('started-*')), first['process'], first['log'])
        # One-CPU hosts intentionally serialize the two gates; a second slot
        # may not be fabricated merely to satisfy the test handshake.
        if first['capacity'] > 1:
            await_value(lambda: list((second['target']/'build').glob('started-*')), second['process'], second['log'])
        for p in (first, second):
            (p['target']/'build').mkdir(exist_ok=True)
            (p['target']/'build/release').touch()
        intervals = {}
        for p in (first, second):
            assert p['process'].wait(timeout=30) == 0, p['log'].read_text()
            observation = json.loads((p['root']/'build/observations.json').read_bytes())
            verify_pool(observation, public_proof(p['profile']))
            for worker in observation['host_pool']['workers'].values():
                for attempt in worker['leases']:
                    intervals.setdefault(attempt['slot'], []).append((attempt['start'], attempt['end']))
            with RuntimeHistory(p['root']) as history:
                assert history.db.execute('SELECT COUNT(*) FROM attempts').fetchone() == (6,)
                assert history.db.execute('SELECT COUNT(*) FROM phases').fetchone() == (18,)
        for rows in intervals.values():
            ordered = sorted(rows)
            assert all(a[1] <= b[0] for a, b in zip(ordered, ordered[1:]))


@pytest.mark.parametrize('proxy', [False, True])
def test_native_lost_worker_is_not_restarted_or_relabelled_as_success(tmp_path, proxy):
    source = 'import os\ndef exercise(index):\n    if index == 0: os._exit(7)\n'
    with pool(tmp_path, proxy=proxy, source=source) as p:
        assert p['process'].wait(timeout=30) != 0, p['log'].read_text()
        path = p['root']/'build/observations.json'
        if path.exists():
            assert not json.loads(path.read_bytes())['suite_passed']
        with RuntimeHistory(p['root']) as history:
            attempts = history.db.execute('SELECT node,complete FROM attempts').fetchall()
            assert ('tests/test_subject.py::test_0', 0) in attempts
            assert len(attempts) == len({n for n, _ in attempts})
            assert history.snapshot(['tests/test_subject.py::test_0'])['tests'][0]['duration_ns'] is None


def test_native_proxy_rejects_changed_python_environment_before_test_body(tmp_path):
    def change_environment(profile):
        profile['environment']['python'] = '0.0.0'
        for worker in profile['workers'].values():
            worker['environment_sha256'] = digest(profile['environment'])
    with pool(tmp_path, transform=change_environment) as p:
        assert p['process'].wait(timeout=30) != 0, p['log'].read_text()
        assert not list((p['target']/'build').glob('started-*'))
        with RuntimeHistory(p['root']) as history:
            assert history.db.execute('SELECT COUNT(*) FROM attempts').fetchone() == (0,)


@pytest.mark.parametrize('proxy', [False, True])
def test_live_drain_preserves_heterogeneous_host_dispatch_and_measurements(tmp_path, proxy):
    def heterogeneous(profile):
        for i, row in enumerate(profile['workers'].values()):
            row.update(host='fast' if i == 0 else 'slow', speed=1.0 if i == 0 else 0.35,
                       resources={**row['resources'], 'workers': 1, 'worker_limit': 1})
    with pool(tmp_path, proxy=proxy, transform=heterogeneous) as p:
        def status():
            return read_status(p['root'], home=p['home'])
        await_value(lambda: len(list((p['target']/'build').glob('started-*'))) == p['capacity'], p['process'], p['log'])
        if p['capacity'] > 1:
            change(p['root'], status()['run'], {'slow': 0}, home=p['home'])
            await_value(lambda: status()['desired']['slow'] == 0, p['process'], p['log'])
        (p['target']/'build/release').touch()
        assert p['process'].wait(timeout=30) == 0, p['log'].read_text()
        observation = json.loads((p['root']/'build/observations.json').read_bytes())
        verify_pool(observation, public_proof(p['profile']))
        with RuntimeHistory(p['root']) as history:
            assert history.db.execute('SELECT COUNT(*),COUNT(DISTINCT node) FROM attempts').fetchone() == (6, 6)
            hosts = {row[0] for row in history.db.execute('SELECT DISTINCT host FROM attempt_hosts')}
            assert hosts == ({'fast', 'slow'} if p['capacity'] > 1 else {'fast'})
