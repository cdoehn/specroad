"""Real worker growth, drain/pause/resume and durable unmodified selection."""
from copy import deepcopy
import json

import pytest

from support.live_pool import pool, await_value, REORDER_COLLECTION
from dev.test_control.store import change, read_status
from dev.test_hosts.contract import public_proof, verify_pool
from verification_support.runtime_history import RuntimeHistory


@pytest.mark.parametrize('proxy', [False, True])
def test_native_pool_drains_all_then_starts_new_workers_without_duplicate_tests(tmp_path, proxy):
    with pool(tmp_path, proxy=proxy, controller_hook=REORDER_COLLECTION) as p:
        root, target, process, log = (p[k] for k in ('root', 'target', 'process', 'log'))
        def status():
            return read_status(root, home=p['home'])
        await_value(lambda: len(list((target/'build').glob('started-*'))) == p['capacity'], process, log)
        run = status()['run']
        change(root, run, {'test-host': 0}, home=p['home'])
        await_value(lambda: status()['desired'] == {'test-host': 0}, process, log)
        assert process.poll() is None  # live bodies were not cancelled
        (target/'build/release').touch()
        await_value(lambda: status()['hosts']['test-host']['processes'] == 0, process, log)
        assert process.poll() is None  # a fully paused pool is not a finished gate
        assert len(list((target/'build').glob('started-*'))) == p['capacity']
        change(root, run, {'test-host': p['capacity']}, home=p['home'])
        assert process.wait(timeout=30) == 0, log.read_text()
        observed = json.loads((root/'build/observations.json').read_bytes())
        assert observed['nodeids'] == list(reversed(p['profile']['selected']))
        assert observed['host_pool']['selected'] == observed['nodeids']
        assert observed['nodeid_to_test_id'] == p['profile']['selected']
        verify_pool(observed, public_proof(p['profile']))
        for mutation in ('input_order', 'grant'):
            bad = deepcopy(observed)
            if mutation == 'input_order':
                bad['host_pool']['selected'] = list(p['profile']['selected'])
            else:
                grant = next(g for values in bad['host_pool']['grants'].values() for g in values)
                grant['index'] = (grant['index'] + 1) % len(observed['nodeids'])
            with pytest.raises(ValueError):
                verify_pool(bad, public_proof(p['profile']))
        assert observed['suite_passed'] and observed['tests_run'] == 6
        initial = set(p['profile']['workers'])
        launched = set(observed['host_pool']['launched'])
        assert len(launched - initial) == p['capacity']
        assert set(observed['workers']) == launched
        # Every resumed body must use an additional, correctly bound gateway.
        body_workers = [(target/'build'/f'started-{i}').read_text() for i in range(6)]
        assert sum(worker in initial for worker in body_workers) == p['capacity']
        assert set(body_workers) - initial <= launched - initial
        with RuntimeHistory(root) as history:
            assert history.db.execute('SELECT COUNT(*),COUNT(DISTINCT node) FROM attempts').fetchone() == (6, 6)
            assert history.db.execute('SELECT COUNT(*) FROM phases').fetchone() == (18,)
            assert history.db.execute('SELECT DISTINCT host FROM attempt_hosts').fetchall() == [('test-host',)]
            assert all(r['duration_ns'] is not None for r in history.snapshot(p['profile']['selected'].values())['tests'])


def test_native_pool_accepts_zero_invocation_override_and_resumes_after_collection(tmp_path):
    with pool(tmp_path, initial=0) as p:
        def status():
            return read_status(p['root'], home=p['home'])
        await_value(lambda: status() and status()['hosts'].get('test-host', {}).get('processes') == 0,
                    p['process'], p['log'])
        assert not list((p['target']/'build').glob('started-*'))
        (p['target']/'build').mkdir(exist_ok=True)
        (p['target']/'build/release').touch()
        change(p['root'], status()['run'], {'test-host': 1}, home=p['home'])
        assert p['process'].wait(timeout=30) == 0, p['log'].read_text()
        observed = json.loads((p['root']/'build/observations.json').read_bytes())
        verify_pool(observed, public_proof(p['profile']))
        assert observed['suite_passed'] and observed['tests_run'] == 6
        initial = set(p['profile']['workers'])
        extra = set(observed['host_pool']['launched']) - initial
        assert len(extra) == 1
        assert {(p['target']/'build'/f'started-{i}').read_text() for i in range(6)} == extra
