"""Real supervised local/proxy copies, fresh fixtures and complete loser cleanup."""
import json
from pathlib import Path

import pytest

from dev.test_hosts.contract import public_proof, verify_pool
from support.live_pool import await_value
from support.move_pool import pool
from verification_support.runtime_history import RuntimeHistory


WAITING_SNAPSHOT = '''import json,pytest
from pathlib import Path
@pytest.hookimpl(trylast=True)
def pytest_sessionstart(session):
    if not hasattr(session.config, 'workerinput'):
        live = session.config._sr_live_pool
        native_permit = live.ds.worker_sr_live_permit
        def observed_permit(node,channel,message):
            folder = Path(session.config.rootpath)/'build'
            if message.get('kind')=='started':
                index=live.moves.current[node.gateway.id]['index']
                if index in live.moves.begun:
                    assert not live.moves.waiting(), 'copy before all originals started'
                    assert not live.ds.sched.pending
                    marker=folder/'copy-start.json'
                    if not marker.exists():
                        pending=marker.with_suffix('.tmp')
                        pending.write_text(json.dumps(dict(started=sorted(live.moves.begun),
                            reclaimed={k:list(v) for k,v in live.ds.sched.reclaimed.items()},
                            workers=sorted(live.rows))))
                        pending.replace(marker)
            native_permit(node,channel,message)
        live.ds.worker_sr_live_permit = observed_permit
'''


@pytest.mark.parametrize('proxy', [False, True])
def test_native_copy_finishes_and_reaps_original_process_tree(tmp_path, proxy):
    # A reserved successor is returned to a free host before any copy starts.
    # The long original remains running until the first complete copy wins.
    with pool(tmp_path/'waiting', proxy=proxy, controller_hook=WAITING_SNAPSHOT,
              transform=lambda p:p.update(format_version=4)) as p:
        await_value(lambda: (p['root']/'build/original').exists(), p['process'], p['log'])
        if p['cpus'] >= 2:
            await_value(lambda: (p['target']/'build/replacement').exists(), p['process'], p['log'], timeout=60)
        else:
            (p['root']/'build/release').touch()
        assert p['process'].wait(timeout=40) == 0, p['log'].read_text()
        result = json.loads((p['root']/'build/observations.json').read_text())
        verify_pool(result, public_proof(p['profile']))
        assert result['suite_passed'] and result['tests_run'] == 6
        assert len(result['copy_winners']) == 6
        original = next(iter(p['profile']['selected']))
        attempts = [r for r in result['copy_attempts'] if r['nodeid'] == original]
        if p['cpus'] >= 2:
            started = json.loads((p['root']/'build/copy-start.json').read_text())
            assert started['started'] == list(range(6))
            assert len(started['reclaimed']['gw0']) == 1
            assert len(started['workers']) == 4  # original pair, returned tail, copy; no respawn churn
            assert len(attempts) == 2 and result['copy_winners'][original] != 'gw0'
            assert result['host_pool']['cancellations']['gw0']['reason'] == 'copy'
            assert not Path('/proc', (p['root']/'build/original-child').read_text()).exists()
            tail = list(p['profile']['selected'])[started['reclaimed']['gw0'][0]]
            assert [r['worker'] for r in result['copy_attempts'] if r['nodeid'] == tail] == ['gw2']
        else:
            assert [r['worker'] for r in attempts] == ['gw0']

    # Two originals give each native worker one final item: both are started
    # before the target becomes idle, satisfying the actual copy precondition.
    with pool(tmp_path/'copy', proxy=proxy, test_count=2, long_identity=True, transform=lambda p:p.update(format_version=4)) as p:
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
