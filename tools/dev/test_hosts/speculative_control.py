"""Controller-owned copy reservations and confirmed loser termination."""
from concurrent.futures import ThreadPoolExecutor

import execnet

from .attempt_control import Attempts
from .speculative_cleanup import CopyCleanup
from .speculative_choice import choose


class CopyAttempts(CopyCleanup, Attempts):
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
                and not any(r['index'] == index and not r['granted'] and r['node'] in self.ds._active_nodes
                            for r in self.copies.values()))

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
                nodeid = choose(host, eligible, rows, identities=self.pool.config._sr_host_profile['selected'])
                if nodeid is None:
                    break
                index = self.ds.sched.collection.index(nodeid)
                self.spawn_copy(host, index, nodeid)

    def spawn_copy(self, host, index, nodeid):
        if not self.host_available(host, index):
            raise ValueError('Test already owns an attempt or reservation on this host')
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
        self.pool.reconcile()  # latest desired counts also govern a held reservation
        slot = message['slot']
        if slot is not None and (type(slot) is not int or not 0 <= slot < self.pool.rows[name]['budget']):
            raise ValueError('Invalid copy host lease')
        allowed = (self.host_available(row['host'], row['index'], exclude=name)
                   and row['index'] not in self.winners and not self.waiting() and self.pending is None
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

    def refresh(self):
        self.reap_pending()
        super().refresh()
        self.dispatch()
