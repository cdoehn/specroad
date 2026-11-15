"""Native phase cancellation and missing transport acknowledgement fail closed."""
import json

import pytest

from dev.test_control.moves import move
from dev.test_control.store import read_status
from dev.test_hosts.contract import public_proof, verify_pool
from support.live_pool import await_value
from support.move_pool import await_source_attempt, await_target_finished, pool, SUBJECT
from verification_support.runtime_history import RuntimeHistory


def source(phase):
    return '''from pathlib import Path
import os,time
import pytest
folder=Path('build')
def pause(phase):
    if os.environ['PYTEST_XDIST_WORKER']=='gw0' and phase==%r:
        folder.mkdir(exist_ok=True); (folder/'phase').write_text(phase)
        deadline=time.monotonic()+50
        while not (folder/'release').exists() and time.monotonic()<deadline: time.sleep(.01)
        assert (folder/'release').exists()
@pytest.fixture(autouse=True)
def fixture(request):
    if request.node.name=='test_0': pause('setup')
    yield
    if request.node.name=='test_0': pause('teardown')
def exercise(index):
    if index==0:
        pause('call')
        if os.environ['PYTEST_XDIST_WORKER']!='gw0':
            folder.mkdir(exist_ok=True); (folder/'replacement').touch()
''' % phase


@pytest.mark.parametrize('phase', ['setup', 'call', 'teardown'])
@pytest.mark.parametrize('proxy', [False, True])
def test_native_move_in_each_pytest_phase_keeps_both_attempts(tmp_path, phase, proxy):
    with pool(tmp_path, proxy=proxy, source=source(phase)) as p:
        def status():
            return read_status(p['root'], home=p['home'])
        await_value(lambda: (p['root']/'build/phase').exists(), p['process'], p['log'])
        if p['cpus'] >= 2:
            await_target_finished(p)
            current,token=await_source_attempt(p)
            move(p['root'], current['run'], token, 'target', home=p['home'])
            await_value(lambda: (p['target']/'build/replacement').exists(), p['process'], p['log'], timeout=60)
        else:
            (p['root']/'build/release').touch()
        assert p['process'].wait(timeout=40) == 0, p['log'].read_text()
        result = json.loads((p['root']/'build/observations.json').read_text())
        verify_pool(result, public_proof(p['profile']))
        if p['cpus'] >= 2:
            with RuntimeHistory(p['root']) as history:
                attempts = history.db.execute("SELECT id,invalid,complete FROM attempts WHERE node LIKE '%::test_0' ORDER BY id").fetchall()
                assert len(attempts) == 2 and attempts[0][1] == 1 and attempts[1][1:] == (0,1)
                old = history.db.execute('SELECT phase FROM phases WHERE attempt=? ORDER BY rowid', (attempts[0][0],)).fetchall()
                assert [r[0] for r in old] == list(('setup','call','teardown')[:('setup','call','teardown').index(phase)])


@pytest.mark.parametrize('proxy', [False, True])
def test_missing_cancel_ack_never_restarts_or_passes_gate(tmp_path, proxy):
    hook = '''import pytest
from pathlib import Path
@pytest.hookimpl(trylast=True)
def pytest_sessionstart(session):
    if not hasattr(session.config,'workerinput'):
        def unavailable(active):
            (Path(session.config.rootpath)/'build/cancel-entered').write_text(active['token'])
            raise ConnectionError('fixture: transport lost before acknowledgement')
        session.config._sr_live_pool.moves.cancel_remote=unavailable
'''
    with pool(tmp_path, proxy=proxy, controller_hook=hook) as p:
        def status():
            return read_status(p['root'], home=p['home'])
        await_value(lambda: (p['root']/'build/original').exists(), p['process'], p['log'])
        if p['cpus'] < 2:
            (p['root']/'build/release').touch()
            assert p['process'].wait(timeout=40) == 0, p['log'].read_text()
            return
        await_target_finished(p)
        current,token=await_source_attempt(p)
        requested=move(p['root'], current['run'], token, 'target', home=p['home'])['request']['id']
        await_value(lambda: status()['moves'].get(requested,{}).get('state')=='rejected', p['process'], p['log'])
        assert (p['root']/'build/cancel-entered').read_text() == token
        assert not (p['target']/'build/replacement').exists()
        (p['root']/'build/release').touch()
        assert p['process'].wait(timeout=40) != 0, p['log'].read_text()
        result = json.loads((p['root']/'build/observations.json').read_text())
        assert not result['suite_passed']
        with pytest.raises(ValueError):
            verify_pool(result, public_proof(p['profile']))
        with RuntimeHistory(p['root']) as history:
            assert history.db.execute("SELECT COUNT(*) FROM attempts WHERE node LIKE '%::test_0'").fetchone() == (1,)


def test_busy_target_rejection_preserves_original_test_and_gate(tmp_path):
    body = SUBJECT.replace("index == 0 and worker == 'gw0'", "index in (0,1) and worker in ('gw0','gw1')")
    with pool(tmp_path, proxy=True, source=body) as p:
        def status():
            return read_status(p['root'], home=p['home'])
        await_value(lambda: (p['root']/'build/original').exists(), p['process'], p['log'])
        if p['cpus'] >= 2:
            await_value(lambda: status()['hosts']['target']['running']==1, p['process'], p['log'])
            current,token=await_source_attempt(p)
            key=move(p['root'], current['run'], token, 'target', home=p['home'])['request']['id']
            await_value(lambda: status()['moves'].get(key,{}).get('state')=='rejected', p['process'], p['log'])
        for root in (p['root'],p['target']):
            (root/'build').mkdir(exist_ok=True); (root/'build/release').touch()
        assert p['process'].wait(timeout=40) == 0, p['log'].read_text()
        with RuntimeHistory(p['root']) as history:
            assert history.db.execute('SELECT COUNT(*),COUNT(DISTINCT node) FROM attempts').fetchone()==(6,6)


def test_completion_during_cancel_request_keeps_real_result_without_repeat(tmp_path):
    hook = '''import pytest,time
from pathlib import Path
@pytest.hookimpl(trylast=True)
def pytest_sessionstart(session):
    if not hasattr(session.config,'workerinput'):
        moves=session.config._sr_live_pool.moves
        def completed(active):
            folder=Path(session.config.rootpath)/'build'
            (folder/'cancel-entered').write_text(active['token'])
            (folder/'release').touch()
            deadline=time.monotonic()+10
            while moves.current.get(active['worker'],{}).get('token') == active['token'] and time.monotonic()<deadline:
                time.sleep(.01)
            assert moves.current.get(active['worker'],{}).get('token') != active['token']
            (folder/'source-completed').write_text(active['token'])
            raise ConnectionError('fixture: worker endpoint closed after ordinary completion')
        moves.cancel_remote=completed
'''
    with pool(tmp_path, proxy=True, controller_hook=hook) as p:
        def status():
            return read_status(p['root'], home=p['home'])
        await_value(lambda: (p['root']/'build/original').exists(), p['process'], p['log'])
        if p['cpus'] >= 2:
            await_target_finished(p)
            current,token=await_source_attempt(p)
            move(p['root'], current['run'], token, 'target', home=p['home'])
        else:
            (p['root']/'build/release').touch()
        assert p['process'].wait(timeout=40)==0, p['log'].read_text()
        if p['cpus'] >= 2:
            assert (p['root']/'build/cancel-entered').read_text() == token
            assert (p['root']/'build/source-completed').read_text() == token
        assert not (p['target']/'build/replacement').exists()
        result = json.loads((p['root']/'build/observations.json').read_text())
        assert result['tests_run'] == 6 and result['suite_passed']
        verify_pool(result, public_proof(p['profile']))
        with RuntimeHistory(p['root']) as history:
            assert history.db.execute("SELECT COUNT(*) FROM attempts WHERE node LIKE '%::test_0'").fetchone()==(1,)


def test_real_call_failure_in_teardown_cannot_be_hidden_by_operator_move(tmp_path):
    body=source('teardown').replace("        pause('call')", "        pause('call')\n        if os.environ['PYTEST_XDIST_WORKER']=='gw0': raise AssertionError('real call failure')")
    with pool(tmp_path, proxy=True, source=body) as p:
        def status():
            return read_status(p['root'], home=p['home'])
        await_value(lambda: (p['root']/'build/phase').exists(), p['process'], p['log'])
        if p['cpus'] >= 2:
            current,token=await_source_attempt(p)
            key=move(p['root'], current['run'], token, 'target', home=p['home'])['request']['id']
            await_value(lambda: status()['moves'].get(key,{}).get('state')=='rejected', p['process'], p['log'])
        (p['root']/'build/release').touch()
        assert p['process'].wait(timeout=40)!=0, p['log'].read_text()
        assert not (p['target']/'build/replacement').exists()
        with RuntimeHistory(p['root']) as history:
            assert history.db.execute("SELECT COUNT(*) FROM attempts WHERE node LIKE '%::test_0'").fetchone()==(1,)
            assert history.db.execute("SELECT COUNT(*) FROM phases WHERE phase='call' AND outcome='failed'").fetchone()==(1,)
