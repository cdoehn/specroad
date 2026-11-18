"""Native races, teardown semantics and lost acknowledgements across the proxy."""
from copy import deepcopy
import json

import pytest

from dev.test_hosts.contract import public_proof, verify_pool
from support.live_pool import await_value
from support.move_pool import pool, SUBJECT
from test_test_control_move_right_integration import source
from verification_support.runtime_history import RuntimeHistory


@pytest.mark.parametrize('phase', ['setup','call','teardown'])
def test_copy_in_each_phase_is_separate_and_proof_rejects_tampering(tmp_path, phase):
    with pool(tmp_path,test_count=2,proxy=True,source=source(phase),transform=lambda p:p.update(format_version=4)) as p:
        await_value(lambda:(p['root']/'build/phase').exists(),p['process'],p['log'])
        if p['cpus']<2: (p['root']/'build/release').touch()
        assert p['process'].wait(timeout=60)==0,p['log'].read_text()
        result=json.loads((p['root']/'build/observations.json').read_text())
        verify_pool(result,public_proof(p['profile']))
        if p['cpus']>=2:
            for mutation in ('winner','token','cleanup','host','phase','permit','duplicate','prior'):
                bad=deepcopy(result)
                node=next(iter(p['profile']['selected']))
                if mutation=='winner': bad['copy_winners'][node]='gw0'
                elif mutation=='token': bad['copy_completions'][0]['token']='f'*32
                elif mutation=='cleanup': bad['host_pool']['cancellations']['gw0']['receipt']['children_remaining']=1
                elif mutation=='host': bad['host_pool']['workers']['gw0']['host']='foreign'
                elif mutation=='phase': next(r for r in bad['copy_attempts'] if r['nodeid']==node and r['state']=='complete')['phases'].pop('teardown')
                elif mutation=='permit': bad['host_pool']['grants']['gw0'][0]['index']=-1
                elif mutation=='duplicate': bad['copy_attempts'].append(deepcopy(bad['copy_attempts'][0]))
                else: bad['host_pool']['cancellations']['gw0']['receipt']['completed'].append({})
                with pytest.raises((ValueError,KeyError,TypeError)): verify_pool(bad,public_proof(p['profile']))


def test_real_failed_copy_is_canonical_failure_and_never_a_measurement(tmp_path):
    body=SUBJECT.replace("(folder/'replacement').write_text(worker)","(folder/'replacement').write_text(worker)\n        raise AssertionError('real copy failure')")
    with pool(tmp_path,test_count=2,proxy=True,source=body,transform=lambda p:p.update(format_version=4)) as p:
        await_value(lambda:(p['root']/'build/original').exists(),p['process'],p['log'])
        if p['cpus']<2:
            (p['root']/'build/release').touch()
            assert p['process'].wait(timeout=40)==0,p['log'].read_text()
            return
        assert p['process'].wait(timeout=60)!=0,p['log'].read_text()
        result=json.loads((p['root']/'build/observations.json').read_text())
        node=next(iter(p['profile']['selected']))
        assert not result['suite_passed'] and result['test_outcomes'][node]=='failed'
        with RuntimeHistory(p['root']) as h:
            assert h.snapshot([node])['tests'][0]['duration_ns'] is None
            assert h.db.execute("SELECT COUNT(*) FROM phases WHERE outcome='failed'").fetchone()==(1,)


def test_missing_termination_ack_keeps_gate_failed_even_with_passing_winner(tmp_path):
    hook='''import json,pytest
from pathlib import Path
@pytest.hookimpl(trylast=True)
def pytest_sessionstart(session):
    if not hasattr(session.config,'workerinput'):
        live=session.config._sr_live_pool
        folder=Path(session.config.rootpath)/'build'
        def unavailable(active):
            (folder/'cancel-entered').touch()
            raise ConnectionError('fixture: missing acknowledgement')
        live.moves.cancel_remote=unavailable
        native_tick=live.ds.worker_sr_live_tick
        def observed_tick():
            native_tick()
            marker=folder/'cancel-error-observed.json'
            if live.errors and not marker.exists():
                node=live.ds.sched.collection[0]
                ledger=live.moves.state.ledger
                winner=ledger.winners.get(node)
                pending=marker.with_suffix('.tmp')
                pending.write_text(json.dumps(dict(
                    stop_requested=bool(live.ds.shouldstop),
                    original_state=ledger.attempts.get((node,'gw0'),{}).get('state'),
                    winner=winner, winner_attempt=ledger.attempts.get((node,winner)))))
                pending.replace(marker)
        live.ds.worker_sr_live_tick=observed_tick
'''
    with pool(tmp_path,test_count=2,proxy=True,controller_hook=hook,transform=lambda p:p.update(format_version=4)) as p:
        await_value(lambda:(p['root']/'build/original').exists(),p['process'],p['log'])
        if p['cpus']>=2:
            await_value(lambda:(p['root']/'build/cancel-entered').exists(),p['process'],p['log'],timeout=60)
            # Entering the RPC is not yet controller failure recognition.
            # Keep the loser running until the native tick records the error;
            # early release would exercise the valid natural-completion race.
            marker=p['root']/'build/cancel-error-observed.json'
            await_value(marker.exists,p['process'],p['log'])
            observed=json.loads(marker.read_text())
            assert observed['stop_requested'] and observed['original_state']=='running'
            assert observed['winner'] not in (None,'gw0')
            assert observed['winner_attempt']['state']=='complete'
            assert observed['winner_attempt']['phases']==dict(setup='passed',call='passed',teardown='passed')
        (p['root']/'build/release').touch()
        code=p['process'].wait(timeout=40)
        assert (code!=0) if p['cpus']>=2 else (code==0),p['log'].read_text()
        if p['cpus']>=2:
            result=json.loads((p['root']/'build/observations.json').read_text())
            assert not result['suite_passed'] and result['host_pool']['errors']
            with pytest.raises(ValueError): verify_pool(result,public_proof(p['profile']))


def test_naturally_completed_loser_is_retained_when_cancel_endpoint_closes(tmp_path):
    hook='''import pytest,time
from pathlib import Path
@pytest.hookimpl(trylast=True)
def pytest_sessionstart(session):
    if not hasattr(session.config,'workerinput'):
        copies=session.config._sr_live_pool.moves
        def completed(active):
            folder=Path(session.config.rootpath)/'build'
            (folder/'release').touch()
            deadline=time.monotonic()+10
            while copies.current.get(active['worker'],{}).get('token')==active['token'] and time.monotonic()<deadline: time.sleep(.01)
            assert copies.current.get(active['worker'],{}).get('token')!=active['token']
            raise ConnectionError('fixture: already completed endpoint')
        copies.cancel_remote=completed
'''
    with pool(tmp_path,test_count=2,proxy=True,controller_hook=hook,transform=lambda p:p.update(format_version=4)) as p:
        await_value(lambda:(p['root']/'build/original').exists(),p['process'],p['log'])
        if p['cpus']<2: (p['root']/'build/release').touch()
        assert p['process'].wait(timeout=60)==0,p['log'].read_text()
        result=json.loads((p['root']/'build/observations.json').read_text())
        verify_pool(result,public_proof(p['profile']))
        if p['cpus']>=2:
            node=next(iter(p['profile']['selected']))
            attempts=[r for r in result['copy_attempts'] if r['nodeid']==node]
            assert len(attempts)==2 and all(r['state']=='complete' for r in attempts)
            assert result['copy_winners'][node]!='gw0'
            # Slot evidence alone is insufficient: merge the two checked host
            # labels in this synthetic negative proof while retaining real,
            # overlapping leases on different native slots.
            bad = deepcopy(result)
            proof = deepcopy(public_proof(p['profile']))
            for row in proof['workers'].values():
                row['host'] = 'same-host'
            bad['host_pool']['binding'] = deepcopy(proof)
            for row in bad['host_pool']['workers'].values():
                row['host'] = 'same-host'
            with pytest.raises(ValueError, match='Same test overlaps'):
                verify_pool(bad, proof)
