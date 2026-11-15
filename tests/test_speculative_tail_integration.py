"""A real prefetched original can change hosts while its predecessor finishes."""
import json

import pytest

from dev.test_hosts.contract import public_proof, verify_pool
from dev.test_control.store import change, read_status
from support.live_pool import await_value
from support.move_pool import pool
from verification_support.runtime_history import RuntimeHistory


SUBJECT = '''from pathlib import Path
import os,time
import pytest
folder=Path('build')
worker=os.environ['PYTEST_XDIST_WORKER']
@pytest.fixture(scope='session',autouse=True)
def session_resource():
    folder.mkdir(exist_ok=True)
    (folder/('session-open-'+worker)).touch()
    yield
    (folder/('session-closed-'+worker)).touch()
@pytest.fixture(scope='module',autouse=True)
def module_resource(session_resource):
    (folder/('module-open-'+worker)).touch()
    yield
    (folder/('module-closed-'+worker)).touch()
    if worker=='gw0' and FAIL_TEARDOWN:
        raise AssertionError('real drained module teardown failure')
def exercise(index):
    (folder/('body-'+str(index)+'-'+worker)).touch()
    if index==0 and worker=='gw0':
        (folder/'original').touch()
        deadline=time.monotonic()+50
        while not (folder/'release').exists() and time.monotonic()<deadline: time.sleep(.01)
        assert (folder/'release').exists()
        if LOSE_PROCESS: os._exit(7)
'''


HOLD_RETURNED_WORKER = '''import os,time,pytest
from pathlib import Path
@pytest.hookimpl(trylast=True)
def pytest_collection_finish(session):
    name=os.environ.get('PYTEST_XDIST_WORKER','')
    if name.startswith('gw') and int(name[2:])>=2:
        folder=Path(session.config.rootpath)/'build'
        folder.mkdir(exist_ok=True)
        (folder/'tail-collecting').touch()
        deadline=time.monotonic()+40
        while not (folder/'allow-tail').exists() and time.monotonic()<deadline: time.sleep(.01)
        assert (folder/'allow-tail').exists()
def pytest_testnodedown(node,error):
    if node.gateway.id=='gw0' and error is None and node.workeroutput.get('exitstatus')==0:
        (Path(node.config.rootpath)/'build/donor-finished').touch()
'''


@pytest.mark.parametrize('proxy', [False, True])
@pytest.mark.parametrize('outcome', ['passed', 'teardown_failure', 'process_loss'])
def test_donor_finishes_during_tail_collection_without_executing_revoked_item(tmp_path, proxy, outcome):
    body = ('FAIL_TEARDOWN = '+repr(outcome == 'teardown_failure')+'\n'
            'LOSE_PROCESS = '+repr(outcome == 'process_loss')+'\n'+SUBJECT)
    with pool(tmp_path, proxy=proxy, source=body, controller_hook=HOLD_RETURNED_WORKER,
              transform=lambda p:p.update(format_version=4)) as p:
        await_value(lambda: (p['root']/'build/original').exists(), p['process'], p['log'])
        try:
            if p['cpus'] >= 2:
                await_value(lambda: (p['target']/'build/tail-collecting').exists(), p['process'], p['log'], timeout=60)
            # Keep the now-draining source disabled after it completes. Only
            # the target owns a live slot, so no valid speculative copy can
            # obscure this exact single-owner/normal-exit regression.
            status = read_status(p['root'], home=p['home'])
            change(p['root'], status['run'], {'source':0}, home=p['home'])
            await_value(lambda: read_status(p['root'], home=p['home'])['desired']['source'] == 0,
                        p['process'], p['log'])
            (p['root']/'build/release').touch()
            if p['cpus'] >= 2 and outcome == 'passed':
                # The old worker must refuse its nextitem even though the new
                # owner has not finished collecting and has not started it.
                await_value(lambda: (p['root']/'build/donor-finished').exists(), p['process'], p['log'])
                assert sorted(f.name for f in (p['root']/'build').glob('body-*-gw0')) == ['body-0-gw0']
                assert (p['root']/'build/module-closed-gw0').exists()
                assert (p['root']/'build/session-closed-gw0').exists()
        finally:
            for root in (p['root'], p['target']):
                (root/'build/allow-tail').touch()
        code = p['process'].wait(timeout=40)
        assert (code == 0) if outcome == 'passed' else (code != 0), p['log'].read_text()
        with RuntimeHistory(p['root']) as h:
            attempts = h.db.execute('SELECT node,worker FROM attempts').fetchall()
            assert len(attempts) == len({n for n, _ in attempts})
            if p['cpus'] >= 2:
                assert [n for n, w in attempts if w == 'gw0'] == [next(iter(p['profile']['selected']))]
        if outcome == 'passed':
            result = json.loads((p['root']/'build/observations.json').read_text())
            verify_pool(result, public_proof(p['profile']))
            assert result['suite_passed'] and result['tests_run'] == 6
            assert not result['host_pool']['errors']
            assert not result['host_pool']['cancellations']
            assert len(result['copy_attempts']) == len(result['copy_winners']) == 6
            for name, row in result['host_pool']['workers'].items():
                folder = (p['target'] if row['host'] == 'target' else p['root'])/'build'
                if row['leases']:
                    assert (folder/('module-closed-'+name)).exists()
                    assert (folder/('session-closed-'+name)).exists()
