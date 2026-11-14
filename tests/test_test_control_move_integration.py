"""Native move: fresh process/fixtures, durable attempts and unchanged gate proof."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from dev.test_control.moves import move
from dev.test_control.store import read_status
from dev.test_hosts.contract import public_proof, verify_pool
from support.live_pool import await_value
from support.move_pool import await_target_finished, pool
from verification_support.runtime_history import RuntimeHistory


@pytest.mark.parametrize('proxy', [False, True])
def test_native_operator_move_reaps_source_and_runs_fresh_target(tmp_path, proxy):
    with pool(tmp_path, proxy=proxy) as p:
        def status():
            return read_status(p['root'], home=p['home'])
        await_value(lambda: (p['root']/'build/original').exists(), p['process'], p['log'])
        view = await_value(lambda: status() if status() and status().get('attempts') else None, p['process'], p['log'])
        token = next(k for k,v in view['attempts'].items() if v['worker'] == 'gw0')
        if p['cpus'] < 2:
            # A single shared CPU slot cannot be reserved while source owns it.
            # Do not manufacture capacity or skip a test in a green gate.
            (p['root']/'build/release').touch()
        else:
            # Short target tests finish before the explicit request. Their
            # completed measurements must survive replacement of the worker.
            await_target_finished(p)
            reply = move(p['root'], view['run'], token, 'target', home=p['home'])
            await_value(lambda: (p['target']/'build/replacement').exists(), p['process'], p['log'], timeout=60)
            assert not Path('/proc', (p['root']/'build/original-child').read_text()).exists()
            with RuntimeHistory(p['root']) as history:
                rows = history.db.execute("SELECT worker,invalid FROM attempts WHERE node LIKE '%::test_0' ORDER BY id").fetchall()
                assert len(rows) == 2 and rows[0] == ('gw0', 1) and rows[1][0] != 'gw0'
            old_fixture = (p['root']/'build/fixture-gw0').read_text()
            new_worker = (p['target']/'build/replacement').read_text()
            assert (p['target']/('build/fixture-'+new_worker)).read_text() != old_fixture
            assert reply['acknowledged'] is False
        assert p['process'].wait(timeout=40) == 0, p['log'].read_text()
        result = json.loads((p['root']/'build/observations.json').read_text())
        assert result['tests_run'] == 6 and result['suite_passed']
        verify_pool(result, public_proof(p['profile']))
        if p['cpus'] >= 2:
            assert len(result['cancelled_attempts']) == 1
            for mutation in ('ack', 'target', 'outcome'):
                bad = deepcopy(result)
                cancelled = next(iter(bad['host_pool']['cancellations'].values()))
                if mutation == 'ack':
                    cancelled['receipt']['children_remaining'] = 1
                elif mutation == 'target':
                    cancelled['target'] = 'foreign'
                else:
                    bad['cancelled_attempts'][0]['phases']['call'] = 'failed'
                with pytest.raises(ValueError):
                    verify_pool(bad, public_proof(p['profile']))
