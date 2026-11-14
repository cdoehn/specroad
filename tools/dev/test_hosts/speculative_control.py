"""Controller-owned copy reservations and confirmed loser termination."""
from concurrent.futures import ThreadPoolExecutor
import json
import time

import execnet

from .attempt_control import Attempts
from .speculative_choice import choose


class CopyAttempts(Attempts):
    speculative = True

    def __init__(self, pool):
        super().__init__(pool)
        self.executor.shutdown(wait=True)
        self.executor = ThreadPoolExecutor(max_workers=min(32, len(pool.rows)), thread_name_prefix='test-copy')
        self.copies, self.killing, self.winners = {}, {}, {}
        self.begun = set()

    @property
    def state(self):
        return self.pool.config._specroad_verification

    @property
    def history(self):
        return self.pool.config._sr_pool_history

    @property
    def busy(self):
        return bool(self.killing or self.pending or any(
            n.gateway.id in self.copies for n in self.ds._active_nodes))

    def waiting(self):
        collection = self.ds.sched.collection
        return collection is None or len(self.begun) != len(collection)

    def can_move(self, attempt):
        index = attempt['index']
        return (sum(r['index'] == index for r in self.current.values()) == 1
                and not any(r['index'] == index and not r['granted'] for r in self.copies.values()))

    def granted(self, name, index, slot):
        token = super().granted(name, index, slot)
        node = self.ds.sched.collection[index]
        self.history.authorize_copy(self.state.history_run, node, name, token)
        self.state.ledger.authorize(node, name, token)
        return token

    def signal(self, node, channel, message):
        super().signal(node, channel, message)
        if message['kind'] == 'started':
            row = self.current[node.gateway.id]
            self.begun.add(row['index'])
            if row['index'] in self.winners:
                self.kill(row)

    def finished(self, name, index):
        row = self.current[name].copy()
        if row['index'] != index or row['state'] != 'finishing':
            raise ValueError('Copy lacks full supervisor completion')
        durable = self.history.complete_copy(self.state.history_run, row['nodeid'], name, row['token'])
        observed = self.state.ledger.completed(row['nodeid'], name, row['token'])
        if durable != observed:
            raise ValueError('Durable and observed copy winners differ')
        if observed:
            self.winners[index] = row
        super().finished(name, index)
        if observed:
            for other in list(self.current.values()):
                if other['index'] == index and other['state'] == 'running':
                    self.kill(other)

    def kill(self, row):
        name = row['worker']
        if name not in self.killing:
            self.pool.retiring.add(name)
            self.killing[name] = dict(source=row.copy(), deadline=time.monotonic()+30,
                                     future=self.executor.submit(self.cancel_remote, row.copy()))

    def dispatch(self):
        if self.waiting() or self.pending is not None or self.ds.shuttingdown or self.ds.shouldstop:
            return
        eligible = {h for h, count in self.pool.owner.desired.items() if count > 0}
        for host in sorted(eligible):
            occupied = sum(self.pool.rows[n.gateway.id]['host'] == host for n in self.ds._active_nodes)
            for _ in range(max(0, self.pool.owner.desired[host] - occupied)):
                rows = [r for r in self.current.values() if r['index'] not in self.winners
                        and self.state.ledger.worst.get(r['nodeid'], 'not_run') in ('not_run', 'passed')]
                rows += [r for r in self.copies.values() if not r['granted'] and r['index'] not in self.winners
                         and r['node'] in self.ds._active_nodes
                         and self.state.ledger.worst.get(r['nodeid'], 'not_run') in ('not_run', 'passed')]
                nodeid = choose(host, eligible, rows)
                if nodeid is None:
                    break
                index = self.ds.sched.collection.index(nodeid)
                self.spawn_copy(host, index, nodeid)

    def spawn_copy(self, host, index, nodeid):
        template = next(r for r in self.pool.rows.values() if r['host'] == host)
        spec = execnet.XSpec(template['spec'])
        spec.execmodel = 'main_thread_only'
        self.ds.nodemanager.group.allocate_id(spec)
        self.pool.rows[spec.id] = template
        # Reservation is visible before setup can enqueue any worker event.
        row = dict(host=host, index=index, nodeid=nodeid, granted=False)
        self.copies[spec.id] = row
        self.reserved[spec.id] = row
        node = self.ds.nodemanager.setup_node(spec, self.ds.queue.put)
        row['node'] = node
        self.ds._active_nodes.add(node)

    def collection(self, node):
        row = self.copies.get(node.gateway.id)
        if row is None:
            return super().collection(node)
        if self.ds.sched.node2collection[node] != self.ds.sched.collection:
            raise ValueError('Copy worker collection differs')
        self.ds.sched.node2pending[node] = [row['index']]
        node.send_runtest_some([row['index']])
        node.shutdown()  # one attempt in a fresh process, complete fixture teardown

    def permit(self, node, channel, message):
        name = node.gateway.id
        row = self.copies.get(name)
        if row is None or row['granted']:
            return super().permit(node, channel, message)
        if (type(message) is not dict or set(message) != {'sequence', 'index', 'slot'}
                or type(message['sequence']) is not int or message['sequence'] != self.pool.sequences.get(name, 0)+1
                or message['index'] != row['index'] or node not in self.ds._active_nodes):
            raise ValueError('Invalid copy reservation permission')
        self.pool.sequences[name] = message['sequence']
        slot = message['slot']
        if slot is not None and (type(slot) is not int or not 0 <= slot < self.pool.rows[name]['budget']):
            raise ValueError('Invalid copy host lease')
        allowed = (row['index'] not in self.winners and not self.waiting() and self.pending is None
                   and self.pool.owner.desired[row['host']] > 0 and name not in self.pool.retiring
                   and not self.ds.shuttingdown and not self.ds.shouldstop
                   and self.state.ledger.worst.get(row['nodeid'], 'not_run') in ('not_run', 'passed'))
        token = None
        if allowed and slot is not None:
            row['granted'] = True
            del self.reserved[name]
            token = self.granted(name, row['index'], slot)
            self.pool.active[name] = row['index']
            self.pool.grants.setdefault(name, []).append(dict(index=row['index'], slot=slot, token=token))
        if not allowed:
            self.pool.retiring.add(name)
        channel.send(dict(sequence=message['sequence'], allowed=allowed, token=token))
        self.pool.publish()
        return True

    def errordown(self, node, error):
        if node.gateway.id in self.killing:
            self.deferred[node.gateway.id] = (node, error)
            return True
        return super().errordown(node, error)

    def reap(self, name, job):
        source = job['source']
        if time.monotonic() > job['deadline']:
            raise ValueError('Copy cancellation confirmation timed out')
        if not job['future'].done():
            return
        receipt = job['future'].result()
        if not receipt.get('cancelled'):
            # A completed protocol can beat the cancel request. It still has
            # to supply normal worker output; no termination is invented.
            if name in self.deferred:
                raise ValueError('Lost worker lacks cancellation confirmation')
            del self.killing[name]
            return
        server = next(s for s in self.pool.config._sr_pool_servers if s.worker == name)
        if name not in self.deferred or not server.closed.is_set():
            return
        if (receipt.get('children_remaining') != 0
                or any(receipt['attempt'].get(k) != source[k] for k in ('token', 'index', 'nodeid', 'slot', 'start'))):
            raise ValueError('Copy termination proof differs from exact loser')
        phases = self.history.cancel_copy(self.state.history_run, source['nodeid'],
            self.pool.config._sr_host_profile['selected'][source['nodeid']], name,
            source['token'], json.dumps(receipt, sort_keys=True))
        self.state.ledger.cancel(source['nodeid'], name, source['token'], phases)
        winner = self.winners[source['index']]
        self.cancelled[name] = dict(receipt=receipt, target=winner['worker'], token=source['token'], reason='copy')
        proof = dict(self.ready[name]['proof'])
        proof['leases'] = [{k: a[k] for k in ('nodeid', 'slot', 'start', 'end', 'token')} for a in receipt['completed']]
        proof['leases'].append({k: receipt['attempt'][k] for k in ('nodeid', 'slot', 'start', 'end', 'token')} | {'cancelled': True})
        self.pool.config._sr_pool_outputs[name] = proof
        node, _ = self.deferred.pop(name)
        self.ds.sched.remove_cancelled(node, source['index'])
        self.ds._active_nodes.remove(node)
        self.pool.active.pop(name, None)
        self.current.pop(name, None)
        del self.killing[name]

    def refresh(self):
        for name, job in list(self.killing.items()):
            try:
                self.reap(name, job)
            except Exception as error:
                self.pool.errors.append('Copy termination failed: ' + str(error))
                self.ds.shouldstop = 'Cannot confirm speculative attempt termination'
                del self.killing[name]
                if name in self.deferred:
                    node, reason = self.deferred.pop(name)
                    self.pool.native_errordown(node, reason)
        super().refresh()
        self.dispatch()
