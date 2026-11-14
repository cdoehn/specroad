"""Reviewed xdist 3.8 main-loop adapter for live host counts, never test retries."""
from queue import Empty
import threading
import types

import execnet
import pytest

from dev.test_control.store import Owner
from .scheduler import HostScheduling


def loop_once(session):
    # DSession's native loop rejects an empty pool. A deliberately paused live
    # pool instead remains in the same gate and accepts operator count changes.
    while True:
        try:
            event, values = session.queue.get(timeout=2)
            break
        except Empty:
            continue
    getattr(session, 'worker_' + event)(**values)
    if session.sched.tests_finished:
        session.triggershutdown()


class LivePool:
    def __init__(self, config):
        self.config = config
        self.rows = dict(config._sr_host_profile['workers'])
        self.retiring, self.active = set(), {}
        self.sequences, self.grants, self.channels = {}, {}, []
        self.stopped = threading.Event()
        self.owner = None
        self.thread = None
        self.errors = []

    @pytest.hookimpl(tryfirst=True)
    def pytest_sessionstart(self, session):
        profile = self.config._sr_host_profile
        options = profile['live']
        capacities = {r['host']: r['resources']['workers'] for r in self.rows.values()}
        self.owner = Owner(options['repository'], capacities, capacities, options['overrides'], home=options['home'])
        self.owner.publish({}, source_sha256=profile['source_sha256'],
                           history_run=self.config._specroad_verification.history_run)
        self.ds = self.config.pluginmanager.getplugin('dsession')
        if self.ds is None:
            raise ValueError('Live pools require the reviewed native xdist controller')
        self.ds.loop_once = types.MethodType(loop_once, self.ds)
        self.ds.worker_sr_live_tick = self.tick
        self.ds.worker_sr_live_permit = self.permit
        self.thread = threading.Thread(target=self.clock, name='specroad-live-control', daemon=True)
        self.thread.start()

    def clock(self):
        while not self.stopped.wait(0.5):
            self.ds.queue.put(('sr_live_tick', {}))

    def connect(self, node):
        channel = node.gateway.newchannel()
        def receive(message):
            if message is not None:
                self.ds.queue.put(('sr_live_permit', dict(node=node, channel=channel, message=message)))
        channel.setcallback(receive, endmarker=None)
        node.workerinput['sr_live_channel'] = channel
        node.workerinput['sr_live'] = True
        self.channels.append(channel)

    def eligible(self, node):
        return node.gateway.id not in self.retiring and not node.shutting_down

    def reconcile(self):
        sched = self.ds.sched
        if self.ds.shuttingdown or sched.collection is None:
            return
        self.owner.refresh()
        for host, wanted in self.owner.desired.items():
            nodes = sorted((n for n in self.ds._active_nodes if self.rows[n.gateway.id]['host'] == host
                            and n.gateway.id not in self.retiring), key=lambda n: int(n.gateway.id[2:]))
            for node in nodes[wanted:]:
                self.retiring.add(node.gateway.id)
                node.shutdown()  # permits current teardown, denies next attempt
            missing = wanted - len(nodes)
            if sched.has_pending:
                for _ in range(max(0, missing)):
                    template = next(r for r in self.rows.values() if r['host'] == host)
                    spec = execnet.XSpec(template['spec'])
                    # NodeManager rebuilds specs lacking this execmodel from
                    # their original text, which does not contain an allocated
                    # id. Normalize before allocating so setup keeps both the
                    # worker identity and its checked host/history binding.
                    spec.execmodel = 'main_thread_only'
                    self.ds.nodemanager.group.allocate_id(spec)
                    self.rows[spec.id] = template
                    node = self.ds.nodemanager.setup_node(spec, self.ds.queue.put)
                    self.ds._active_nodes.add(node)

    def publish(self):
        hosts = {}
        for host in self.owner.capacities:
            nodes = [n for n in self.ds._active_nodes if self.rows[n.gateway.id]['host'] == host]
            hosts[host] = dict(processes=len(nodes), running=sum(n.gateway.id in self.active for n in nodes),
                               draining=sum(n.gateway.id in self.retiring for n in nodes))
        self.owner.publish(hosts)

    def tick(self):
        try:
            self.reconcile()
            if self.ds.sched.collection is not None:
                self.ds.sched.check_schedule()
            self.publish()
        except (ValueError, OSError, KeyError, TypeError) as error:
            self.errors.append(str(error))
            self.ds.shouldstop = 'Live host control failed: ' + str(error)

    def permit(self, node, channel, message):
        name = node.gateway.id
        try:
            if (node not in self.ds._active_nodes or name not in self.rows
                    or type(message) is not dict or set(message) != {'sequence', 'index', 'slot'}
                    or type(message['sequence']) is not int or message['sequence'] != self.sequences.get(name, 0)+1
                    or type(message['index']) is not int):
                raise ValueError('Invalid live worker permission request')
            self.sequences[name] = message['sequence']
            self.reconcile()
            pending = self.ds.sched.node2pending[node]
            if not pending or pending[0] != message['index'] or name in self.active:
                raise ValueError('Worker permission differs from the fixed selection')
            slot = message['slot']
            if slot is not None and (type(slot) is not int or not 0 <= slot < self.rows[name]['budget']):
                raise ValueError('Invalid atomic host slot')
            allowed = self.eligible(node) and not self.ds.shuttingdown
            # A normal tail shutdown only supplies xdist's nextitem sentinel;
            # it does not cancel the final queued item.
            if name not in self.retiring and not self.ds.shuttingdown:
                allowed = True
            if self.ds.shuttingdown:
                self.retiring.add(name)
            if allowed and slot is not None:
                self.active[name] = message['index']
                self.grants.setdefault(name, []).append(dict(index=message['index'], slot=slot))
            channel.send(dict(sequence=message['sequence'], allowed=allowed))
            self.publish()
        except (ValueError, OSError, KeyError, TypeError) as error:
            self.errors.append(str(error))
            channel.send(dict(sequence=message.get('sequence') if type(message) is dict else None, allowed=False))
            self.ds.shouldstop = 'Live worker permission failed'

    def close(self):
        self.stopped.set()
        if self.thread is not None:
            self.thread.join(timeout=2)
        if self.owner is not None:
            self.owner.close()

    def pytest_unconfigure(self, config):
        self.close()


class LiveScheduling(HostScheduling):
    def __init__(self, config, log=None):
        super().__init__(config, log)
        self.control = config._sr_live_pool

    def host(self, node):
        return self.control.rows[node.gateway.id]

    def scheduling_nodes(self):
        return [n for n in self.nodes if self.control.eligible(n) and n in self.node2collection]

    @property
    def tests_finished(self):
        return self.collection is not None and not self.has_pending

    def check_schedule(self):
        self.control.reconcile()
        super().check_schedule()

    def mark_test_complete(self, node, item_index, duration=None):
        if self.control.active.pop(node.gateway.id, None) != item_index:
            raise ValueError('Completed test lacks its live permission')
        super().mark_test_complete(node, item_index, duration)

    def remove_node(self, node):
        name = node.gateway.id
        if name in self.control.retiring and name not in self.control.active and getattr(node, 'workeroutput', {}).get('exitstatus') == 0:
            reserved = self.node2pending.pop(node)
            self.started.pop(node, None)
            for index in reserved:
                if index in self.pending:
                    raise ValueError('Duplicate returned live reservation')
                self.pending.append(index)
                self.remaining.add(index)
                self.remaining_work += self.work_weights[index]
                if self.identity(index) not in self.profile['baseline']:
                    self.unknown.append(index)
                else:
                    import heapq
                    weight = self.profile['baseline'][self.identity(index)]
                    heapq.heappush(self.long, (-weight, index))
                    heapq.heappush(self.short, (weight, index))
            self.check_schedule()
            return None
        return super().remove_node(node)
