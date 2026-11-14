"""Real supervised local/proxy copies, fresh fixtures and complete loser cleanup."""
import json
from pathlib import Path

import pytest

from dev.test_hosts.contract import public_proof, verify_pool
from support.live_pool import await_value
from support.move_pool import pool, await_target_finished
from verification_support.runtime_history import RuntimeHistory


WAITING_SNAPSHOT = '''import json,pytest
from pathlib import Path
@pytest.hookimpl(trylast=True)
def pytest_sessionstart(session):
    if not hasattr(session.config, 'workerinput'):
        live = session.config._sr_live_pool
        native_tick = live.ds.worker_sr_live_tick
        def observed_tick():
            native_tick()
            folder = Path(session.config.rootpath)/'build'
            if ((folder/'original').exists() and (folder/'initial-target-finished').exists()
                    and live.moves.waiting() and not (folder/'waiting-snapshot.json').exists()):
                pending = folder/'waiting-snapshot.tmp'
                pending.write_text(json.dumps(dict(
                    workers=sorted(live.rows), started=len(live.moves.begun))))
                pending.replace(folder/'waiting-snapshot.json')
        live.ds.worker_sr_live_tick = observed_tick
'''


@pytest.mark.parametrize('proxy', [False, True])
def test_native_copy_finishes_and_reaps_original_process_tree(tmp_path, proxy):
    # Keep the six-test case: one original remains reserved behind the long
    # first test, so duplication must wait and idle workers must not churn.
    with pool(tmp_path/'waiting', proxy=proxy, controller_hook=WAITING_SNAPSHOT,
              transform=lambda p:p.update(format_version=4)) as p:
        await_value(lambda: (p['root']/'build/original').exists(), p['process'], p['log'])
        if p['cpus'] >= 2:
            await_target_finished(p)
            marker = p['root']/'build/waiting-snapshot.json'
            await_value(lambda: marker.exists() and marker.stat().st_size > 0, p['process'], p['log'])
            waiting = json.loads(marker.read_text())
            assert waiting['workers'] == ['gw0', 'gw1'] and waiting['started'] < 6
            assert not (p['target']/'build/replacement').exists()
        (p['root']/'build/release').touch()
        assert p['process'].wait(timeout=40) == 0, p['log'].read_text()
        result = json.loads((p['root']/'build/observations.json').read_text())
        verify_pool(result, public_proof(p['profile']))
        assert result['suite_passed'] and result['tests_run'] == 6
        assert len(result['copy_winners']) == 6
        original = next(iter(p['profile']['selected']))
        assert [r['worker'] for r in result['copy_attempts'] if r['nodeid'] == original] == ['gw0']

    # Two originals give each native worker one final item: both are started
    # before the target becomes idle, satisfying the actual copy precondition.
    with pool(tmp_path/'copy', proxy=proxy, test_count=2, transform=lambda p:p.update(format_version=4)) as p:
        await_value(lambda: (p['root']/'build/original').exists(), p['process'], p['log'])
        if p['cpus'] < 2:
            (p['root']/'build/release').touch()
        else:
            await_value(lambda: (p['target']/'build/replacement').exists(), p['process'], p['log'], timeout=60)
        assert p['process'].wait(timeout=40) == 0, p['log'].read_text()
        result = json.loads((p['root']/'build/observations.json').read_text())
        assert result['suite_passed'] and result['tests_run'] == 2
        assert len(result['copy_winners']) == 2
        verify_pool(result, public_proof(p['profile']))
        if p['cpus'] >= 2:
            assert not Path('/proc', (p['root']/'build/original-child').read_text()).exists()
            node = next(iter(p['profile']['selected']))
            winner = result['copy_winners'][node]
            assert winner != 'gw0'
            assert (p['target']/('build/fixture-'+winner)).read_text() != (p['root']/'build/fixture-gw0').read_text()
            assert result['host_pool']['cancellations']['gw0']['reason'] == 'copy'
            with RuntimeHistory(p['root']) as history:
                rows = history.db.execute('SELECT worker,invalid FROM attempts WHERE node=? ORDER BY id', (node,)).fetchall()
                assert rows == [('gw0',1), (winner,0)]
                assert history.snapshot([node])['tests'][0]['duration_ns'] is not None
