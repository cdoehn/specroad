"""Actual late worker collection must not restart an already completed test."""
import json

from support.live_pool import await_value
from support.move_pool import pool
from dev.test_hosts.contract import public_proof, verify_pool


def test_winner_before_copy_collection_denies_execution_without_losing_coverage(tmp_path):
    hook='''import os,time
from pathlib import Path
import pytest
@pytest.hookimpl(trylast=True)
def pytest_collection_finish(session):
    name=os.environ.get('PYTEST_XDIST_WORKER','')
    if name.startswith('gw') and int(name[2:])>=2:
        folder=Path(session.config.rootpath)/'build'; folder.mkdir(exist_ok=True)
        (folder/'copy-collecting').touch()
        deadline=time.monotonic()+40
        while not (folder/'allow-copy').exists() and time.monotonic()<deadline: time.sleep(.01)
        assert (folder/'allow-copy').exists()
def pytest_testnodedown(node,error):
    if node.gateway.id=='gw0' and error is None and node.workeroutput.get('exitstatus')==0:
        (Path(node.config.rootpath)/'build/source-finished').touch()
'''
    with pool(tmp_path,test_count=2,proxy=True,controller_hook=hook,transform=lambda p:p.update(format_version=4)) as p:
        await_value(lambda:(p['root']/'build/original').exists(),p['process'],p['log'])
        if p['cpus']>=2:
            await_value(lambda:(p['target']/'build/copy-collecting').exists(),p['process'],p['log'],timeout=60)
        (p['root']/'build/release').touch()
        if p['cpus']>=2:
            await_value(lambda:(p['root']/'build/source-finished').exists(),p['process'],p['log'])
            (p['target']/'build/allow-copy').touch()
        assert p['process'].wait(timeout=40)==0,p['log'].read_text()
        result=json.loads((p['root']/'build/observations.json').read_text())
        verify_pool(result,public_proof(p['profile']))
        assert len(result['copy_attempts'])==2
        assert result['copy_winners'][next(iter(p['profile']['selected']))]=='gw0'
        assert not (p['target']/'build/replacement').exists()
