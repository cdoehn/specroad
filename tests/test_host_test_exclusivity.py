"""One exact test per host, including reservations and unfinished cleanup."""
from types import SimpleNamespace

import pytest

from dev.test_hosts.attempt_control import Attempts
from dev.test_hosts.speculative_control import CopyAttempts
from test_remote_test_hosts import Node, Reply


def controller():
    moves = object.__new__(CopyAttempts)
    hosts = ('blade', 'thinkpad', 'desktop', 'desktop1', 'desktop2')
    nodes = {Node('gw0')}
    selected = {'tests/test_one.py::test_one': 'one'}
    sched = SimpleNamespace(collection=list(selected))
    moves.pool = SimpleNamespace(
        rows={'gw0': dict(host='blade', budget=12)}, active={}, retiring=set(), sequences={}, grants={},
        ds=SimpleNamespace(sched=sched, _active_nodes=nodes, shouldstop=False, shuttingdown=False),
        owner=SimpleNamespace(desired=dict.fromkeys(hosts, 10)), publish=lambda:None, reconcile=lambda:None,
        config=SimpleNamespace(_sr_host_profile=dict(selected=selected),
                               _specroad_verification=SimpleNamespace(ledger=SimpleNamespace(worst={}))))
    moves.current = {'gw0': dict(host='blade', index=0, nodeid=next(iter(selected)), state='running')}
    moves.copies, moves.reserved, moves.winners, moves.ready = {}, {}, {}, {}
    moves.pending, moves.begun = None, {0}
    return moves


def test_many_free_slots_reserve_exactly_one_copy_on_each_other_host():
    moves = controller()
    issued = []
    def reserve(host, index, nodeid):
        name = 'gw' + str(len(issued) + 1)
        node = Node(name)
        row = dict(host=host, index=index, nodeid=nodeid, granted=False, node=node)
        moves.pool.rows[name] = dict(host=host, budget=10)
        moves.copies[name] = moves.reserved[name] = row
        moves.ds._active_nodes.add(node)
        issued.append(host)
    moves.spawn_copy = reserve
    moves.dispatch()
    moves.dispatch()  # another controller event cannot reuse those reservations
    assert sorted(issued) == ['desktop', 'desktop1', 'desktop2', 'thinkpad']
    assert len(moves.current) + len(moves.reserved) == 5


@pytest.mark.parametrize('state', ['starting', 'running', 'finishing'])
def test_unfinished_original_denies_a_second_worker_even_on_another_slot(state):
    moves = controller()
    moves.current['gw0']['state'] = state
    moves.pool.rows['gw1'] = dict(host='blade', budget=12)
    moves.ready['gw1'] = {}
    before = moves.current.copy()
    with pytest.raises(ValueError, match='already owns'):
        Attempts.granted(moves, 'gw1', 0, 7)
    assert moves.current == before
    assert not moves.pool.grants


def test_reservation_rejects_direct_spawn_before_a_gateway_is_allocated():
    moves = controller()
    moves.reserved['gw1'] = dict(host='desktop', index=0)
    with pytest.raises(ValueError, match='already owns'):
        moves.spawn_copy('desktop', 0, moves.ds.sched.collection[0])
    assert not moves.copies


def test_copy_permit_rechecks_the_host_and_denies_a_competing_reservation():
    moves = controller()
    node = Node('gw1')
    moves.ds._active_nodes.add(node)
    moves.pool.rows['gw1'] = dict(host='desktop', budget=10)
    row = dict(host='desktop', index=0, nodeid=moves.ds.sched.collection[0], granted=False, node=node)
    moves.copies['gw1'] = moves.reserved['gw1'] = row
    moves.reserved['gw2'] = dict(host='desktop', index=0)
    reply = Reply()
    assert moves.permit(node, reply, dict(sequence=1, index=0, slot=0))
    assert reply.replies == [dict(sequence=1, allowed=False, token=None)]
    assert 'gw1' in moves.pool.retiring and not row['granted']
    assert not moves.pool.grants
