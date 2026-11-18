"""Reservation lifetime, parameter identity and independent native evidence."""
import json

import pytest

from dev.test_hosts.attempt_control import Attempts
from dev.test_hosts.contract import public_proof, verify_pool
from dev.test_hosts.speculative_choice import choose
from support.live_pool import await_value
from support.move_pool import pool, SUBJECT
from test_host_test_exclusivity import controller
from test_remote_test_hosts import Node


def test_confirmed_completion_releases_host_but_a_new_run_has_no_old_reservation():
    moves = controller()
    moves.current['gw0']['state'] = 'finishing'
    assert not moves.host_available('blade', 0)
    Attempts.finished(moves, 'gw0', 0)
    assert moves.host_available('blade', 0)
    fresh = controller()
    fresh.current.clear()
    assert fresh.host_available('blade', 0)


def test_move_reservation_counts_until_its_worker_has_confirmed_exit():
    moves = controller()
    node = Node('gw1')
    moves.ds._active_nodes.add(node)
    moves.reserved['gw1'] = dict(target='desktop', source=dict(index=0), node=node)
    assert not moves.host_available('desktop', 0)
    assert moves.host_available('desktop', 1)
    assert moves.host_available('desktop', 0, exclude='gw1')
    moves.ds._active_nodes.remove(node)
    assert moves.host_available('desktop', 0)


def test_parameter_variants_and_newly_enabled_hosts_remain_eligible():
    active = [dict(nodeid='test[x]', host='one'), dict(nodeid='test[y]', host='two')]
    assert choose('one', {'one', 'two'}, active) == 'test[y]'
    active.append(dict(nodeid='test[y]', host='one'))
    assert choose('one', {'one', 'two'}, active) is None
    assert choose('three', {'one', 'two'}, active) is None
    assert choose('three', {'one', 'two', 'three'}, active) == 'test[x]'
    assert choose('two', {'one', 'two', 'three'}, active, waiting=True) is None


OBSERVE = '''import json,pytest
from pathlib import Path
@pytest.hookimpl(trylast=True)
def pytest_sessionstart(session):
    if not hasattr(session.config,'workerinput'):
        live=session.config._sr_live_pool
        native=live.ds.worker_sr_live_tick
        seen=[0]
        def tick():
            native()
            rows=list(live.moves.current.values())
            keys=[(row['host'],row['index']) for row in rows]
            assert len(keys)==len(set(keys)), 'same test running twice on one host'
            if sum(row['index']==0 and row['state']=='running' for row in rows)==2:
                seen[0]+=1
                if seen[0]>=3:
                    for row in live.rows.values():
                        folder=Path(row['root'])/'build'
                        (folder/'host-limit-observed.json').write_text(json.dumps(keys))
                        (folder/'release').touch()
        live.ds.worker_sr_live_tick=tick
'''


@pytest.mark.parametrize('proxy', [False, True])
def test_native_pool_leaves_extra_slots_free_after_all_hosts_have_the_test(tmp_path, proxy):
    # Both attempts stay alive for multiple controller ticks. This exposes
    # the old "all hosts covered => fill every slot" rule without a timing race.
    source = SUBJECT.replace("(folder/'replacement').write_text(worker)", """(folder/'replacement').write_text(worker)
        deadline=time.monotonic()+40
        while not (folder/'release').exists() and time.monotonic()<deadline: time.sleep(.01)
        assert (folder/'release').exists()""")
    def profile(value):
        value['format_version'] = 4
        for row in value['workers'].values():
            if row['resources']['available_cpus'] >= 4:
                row['resources'].update(workers=2, worker_limit=2)
                row['budget'] = 4
        if value['workers']['gw0']['resources']['workers'] == 2:
            value['workers']['gw2'] = dict(value['workers']['gw0'])
            value['workers']['gw3'] = dict(value['workers']['gw1'])
    with pool(tmp_path, test_count=2, proxy=proxy, source=source,
              transform=profile, controller_hook=OBSERVE) as p:
        await_value(lambda:(p['root']/'build/original').exists(), p['process'], p['log'])
        if p['cpus'] < 2:
            (p['root']/'build/release').touch()
        assert p['process'].wait(timeout=60) == 0, p['log'].read_text()
        result = json.loads((p['root']/'build/observations.json').read_text())
        verify_pool(result, public_proof(p['profile']))
        node = next(iter(p['profile']['selected']))
        attempts = [r for r in result['copy_attempts'] if r['nodeid'] == node]
        assert len(attempts) == (2 if p['cpus'] >= 2 else 1)
        if p['cpus'] >= 2:
            assert (p['root']/'build/host-limit-observed.json').is_file()
            hosts = [result['host_pool']['workers'][row['worker']]['host'] for row in attempts]
            assert sorted(hosts) == ['source', 'target']
