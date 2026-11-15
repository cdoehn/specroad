"""Controller ownership boundaries for returning unstarted prefetched items."""
from types import SimpleNamespace

import pytest

from dev.test_hosts.live import LivePool
from dev.test_hosts.live_scheduler import LiveScheduling
from test_remote_test_hosts import Node, Reply


def reservation(*, unknown=False):
    # Real scheduler/permit methods; only xdist transport and operator IO are
    # tiny adapters. End-to-end worker/fixture proof is in the native tests.
    sched = object.__new__(LiveScheduling)
    pool = object.__new__(LivePool)
    node = Node('gw0')
    sched.control = pool
    sched.collection = ['long', 'tail']
    sched.node2pending = {node: [0, 1]}
    sched.node2collection = {node: sched.collection}
    sched.pending, sched.unknown, sched.long, sched.short = [], [], [], []
    sched.remaining, sched.reclaimed, sched.started = set(), {}, {node: 0.0}
    sched.ready, sched.remaining_work = True, 0.0
    sched.work_weights = {0: 100.0, 1: 1.0}
    sched.profile = dict(selected={'long':'long', 'tail':'tail'}, baseline={} if unknown else {'tail':1.0})
    pool.rows = {'gw0':dict(host='source', budget=1), 'gw1':dict(host='target', budget=1)}
    pool.active, pool.retiring = {'gw0':0}, set()
    pool.owner = SimpleNamespace(desired={'source':1, 'target':1}, refresh=lambda:None)
    pool.ds = SimpleNamespace(sched=sched, _active_nodes={node}, shuttingdown=False, shouldstop=False)
    pool.moves = SimpleNamespace(speculative=True, pending=None, begun={0}, copies={}, reserved={}, killing={},
        current={'gw0':dict(index=0, state='running')}, waiting=lambda:True, holds=lambda h:False,
        permit=lambda *a:False)
    pool.sequences, pool.grants, pool.errors = {}, {}, []
    pool.publish = lambda:None
    return sched, pool, node


@pytest.mark.parametrize('unknown', [False, True])
def test_return_is_once_and_denies_old_start_before_new_owner_can_run(unknown):
    sched, pool, donor = reservation(unknown=unknown)
    assert sched.release_tail()
    assert pool.active == {'gw0':0} and pool.moves.current['gw0']['state'] == 'running'
    assert sched.node2pending[donor] == [0] and sched.reclaimed == {'gw0':(1,)}
    assert sched.pending == [1] and sched.remaining == {1} and sched.remaining_work == 1.0
    assert donor.shutting_down and pool.retiring == {'gw0'}
    assert sched.unknown == ([1] if unknown else [])
    assert sched.long == ([] if unknown else [(-1.0, 1)])
    assert not sched.release_tail()
    with pytest.raises(ValueError, match='before predecessor completion'):
        sched.denies_reclaimed(donor, 1)
    # Completion wins the race with the new worker's collection. The donor
    # gets a valid denial, not an unknown-index error and not a new grant.
    pool.active.clear()
    pool.moves.current.clear()
    sched.node2pending[donor].clear()
    pool.owner.desired['target'] = 0
    reply = Reply()
    pool.permit(donor, reply, dict(sequence=1, index=1, slot=None))
    assert reply.replies == [dict(sequence=1, allowed=False, token=None)]
    assert not pool.errors and not pool.ds.shouldstop and not pool.grants
    assert sched.pending == [1]  # denial cannot return it a second time
    pool.owner.desired['source'] = 0
    donor.workeroutput = {'exitstatus':0}
    sched.remove_node(donor)
    assert sched.pending == [1] and sched.reclaimed == {}


@pytest.mark.parametrize('boundary', ['global_queue', 'paused', 'occupied', 'move', 'stop',
    'shutdown', 'no_copies', 'all_started', 'not_running', 'cancelled', 'copy_worker', 'move_worker'])
def test_tail_stays_owned_when_handoff_is_not_eligible(boundary):
    sched, pool, donor = reservation()
    if boundary == 'global_queue': sched.pending.append(2)
    elif boundary == 'paused': pool.owner.desired = {'source':0, 'target':0}
    elif boundary == 'occupied': pool.ds._active_nodes.add(Node('gw1'))
    elif boundary == 'move': pool.moves.pending = {'state':'draining_target'}
    elif boundary == 'stop': pool.ds.shouldstop = 'failed test'
    elif boundary == 'shutdown': pool.ds.shuttingdown = True
    elif boundary == 'no_copies': pool.moves.speculative = False
    elif boundary == 'all_started': pool.moves.waiting = lambda:False
    elif boundary == 'not_running': pool.moves.current['gw0']['state'] = 'finishing'
    elif boundary == 'cancelled': pool.moves.killing['gw0'] = {}
    elif boundary == 'copy_worker': pool.moves.copies['gw0'] = {}
    elif boundary == 'move_worker': pool.moves.reserved['gw0'] = {}
    before = list(sched.pending)
    assert not sched.release_tail()
    assert sched.pending == before and sched.node2pending[donor] == [0, 1]
    assert not sched.reclaimed and not donor.shutting_down


@pytest.mark.parametrize('corruption', ['started', 'returned'])
def test_inconsistent_tail_is_never_reassigned(corruption):
    sched, pool, donor = reservation()
    if corruption == 'started': pool.moves.begun.add(1)
    else: sched.remaining.add(1)
    with pytest.raises(ValueError, match='already started or returned'):
        sched.release_tail()
    assert not sched.reclaimed and sched.node2pending[donor] == [0, 1]


@pytest.mark.parametrize('permission', [dict(sequence=1, index=42, slot=None),
    dict(sequence=1, index=1, slot=1), dict(sequence=2, index=1, slot=None)])
def test_returned_permission_still_rejects_wrong_index_slot_or_sequence(permission):
    sched, pool, donor = reservation()
    assert sched.release_tail()
    pool.active.clear(); pool.moves.current.clear()
    sched.node2pending[donor].clear()
    pool.owner.desired['target'] = 0
    reply = Reply()
    pool.permit(donor, reply, permission)
    assert pool.errors and pool.ds.shouldstop and not pool.grants
    assert reply.replies[-1]['allowed'] is False
