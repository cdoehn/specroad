"""Explicit move lifecycle on xdist's controller thread, never automatic retries."""
from concurrent.futures import ThreadPoolExecutor
import json
import re
import time
import uuid

import execnet

from dev.test_control.moves import requests
from .host_exclusivity import host_available


class Attempts:
    def __init__(self, pool):
        self.pool = pool
        self.ready, self.current, self.receipts = {}, {}, {}
        self.reserved, self.cancelled, self.deferred = {}, {}, {}
        self.pending = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='test-move')

    @property
    def ds(self):
        return self.pool.ds

    def holds(self, host):
        return self.pending is not None and host == self.pending['target']

    def public(self):
        return {r['token']: {k: r[k] for k in ('nodeid', 'host', 'worker', 'state')}
                for r in self.current.values() if r['state'] == 'running'}

    def host_available(self, host, index, *, exclude=None):
        return host_available(host, index, self.current, self.reserved,
                              self.ds._active_nodes, exclude=exclude)

    def granted(self, name, index, slot):
        if name not in self.ready or name in self.current:
            raise ValueError('Attempt needs its current supervised worker binding')
        if not self.host_available(self.pool.rows[name]['host'], index, exclude=name):
            raise ValueError('Test already owns an attempt or reservation on this host')
        token = uuid.uuid4().hex
        self.current[name] = dict(token=token, index=index, slot=slot, worker=name,
            nodeid=self.ds.sched.collection[index], host=self.pool.rows[name]['host'], state='starting')
        return token

    def signal(self, node, channel, message):
        name = node.gateway.id
        if (node not in self.ds._active_nodes or name not in self.pool.rows
                or type(message) is not dict or set(message) != {'sequence', 'kind', 'value'}
                or type(message['sequence']) is not int
                or message['sequence'] != self.pool.sequences.get(name, 0) + 1):
            raise ValueError('Invalid attempt event sequence')
        self.pool.sequences[name] = message['sequence']
        kind, value = message['kind'], message['value']
        if kind == 'ready':
            if name in self.ready or type(value) is not dict or set(value) != {'endpoint', 'secret', 'proof'}:
                raise ValueError('Invalid worker supervisor binding')
            from verification_support.host_execution import verify_resources
            expected = self.pool.rows[name]
            profile = self.pool.config._sr_host_profile
            proof = value['proof']
            if (type(proof) is not dict or proof.get('leases') != []
                    or any(proof.get(k) != expected[k] for k in ('host', 'hostname', 'account', 'environment_sha256'))
                    or any(proof.get(k) != profile[k] for k in ('source_sha256', 'snapshot_sha256'))
                    or proof.get('io_priority') != {'class': 2, 'priority': 7}
                    or type(value['endpoint']) is not str or type(value['secret']) is not str
                    or not re.fullmatch('[0-9a-f]{32}', value['secret'])):
                raise ValueError('Supervisor does not belong to the approved worker')
            verify_resources({'host_resources': proof.get('resources'), 'workers': list(range(expected['resources']['workers']))}, expected['resources'])
            self.ready[name] = value
        elif kind in ('started', 'complete'):
            active = self.current.get(name)
            field = 'start' if kind == 'started' else 'end'
            if (type(value) is not dict or set(value) != {'token', field} or active is None
                    or value.get('token') != active['token'] or type(value[field]) is not int or value[field] < 0
                    or active['state'] != ('starting' if kind == 'started' else 'running')
                    or kind == 'complete' and value['end'] < active['start']):
                raise ValueError('Attempt checkpoint does not match permission')
            if kind == 'started':
                active.update(start=value['start'], state='running')
            else:
                active.update(end=value['end'], state='finishing')
        else:
            raise ValueError('Unknown attempt event')
        channel.send(dict(sequence=message['sequence'], acknowledged=True))
        self.pool.publish()

    def finished(self, name, index):
        active = self.current.get(name)
        if active is None or active['index'] != index or active['state'] != 'finishing':
            raise ValueError('Attempt completed without supervisor checkpoint')
        del self.current[name]

    def refresh(self):
        self.pool.owner.refresh()
        if self.ds.shuttingdown or self.ds.shouldstop:
            if self.pending is not None and self.pending['state'] == 'cancelling':
                self.advance()
            elif self.pending is not None:
                self.reject(self.pending, 'Gate is stopping')
                self.deny_target(self.pending)
                self.pending = None
            return
        if self.pending is not None:
            self.advance()
            return
        for row in requests(self.pool.owner.root, self.pool.owner.run)['requests']:
            if row['id'] in self.receipts:
                continue
            self.receipts[row['id']] = {**row, 'state': 'checking'}
            found = next((r for r in self.current.values() if r['token'] == row['attempt'] and r['state'] == 'running'), None)
            if (found is None or not self.can_move(found) or row['target'] not in self.pool.owner.capacities or self.pool.owner.desired.get(row['target'], 0) == 0
                    or self.pool.config._specroad_verification.ledger.worst.get(found['nodeid'], 'passed') != 'passed'):
                self.reject(row, 'Attempt finished or target is no longer enabled')
                continue
            if not self.host_available(row['target'], found['index']):
                self.reject(row, 'Test already owns the target host')
                continue
            nodes = [n for n in self.ds._active_nodes if self.pool.rows[n.gateway.id]['host'] == row['target']]
            idle = next((n for n in nodes if n.gateway.id not in self.pool.active
                         and n.gateway.id not in self.pool.retiring), None)
            if idle is None and len(nodes) >= self.pool.owner.desired[row['target']]:
                self.reject(row, 'Target host has no free worker')
                continue
            self.pending = {**row, 'source': found.copy(), 'deadline': time.monotonic() + 120,
                            'state': 'draining_target', 'old_target': idle}
            if idle is not None:
                self.pool.retiring.add(idle.gateway.id)
                idle.shutdown()
            self.advance()
            break

    def can_move(self, attempt):
        return True

    def reject(self, row, reason):
        self.receipts[row['id']] = {k: row[k] for k in ('id', 'attempt', 'target')} | dict(state='rejected', reason=reason)

    def spawn_target(self, pending):
        template = next(r for r in self.pool.rows.values() if r['host'] == pending['target'])
        spec = execnet.XSpec(template['spec'])
        spec.execmodel = 'main_thread_only'
        self.ds.nodemanager.group.allocate_id(spec)
        self.pool.rows[spec.id] = template
        pending.update(state='reserving', worker=spec.id)
        self.reserved[spec.id] = pending
        node = self.ds.nodemanager.setup_node(spec, self.ds.queue.put)
        self.ds._active_nodes.add(node)
        pending['node'] = node

    def collection(self, node):
        pending = self.reserved.get(node.gateway.id)
        if pending is None:
            return
        if self.ds.sched.node2collection[node] != self.ds.sched.collection:
            raise ValueError('Move target collection differs')
        # Reservation only: the duplicate index cannot receive an execution
        # permission until the source tree is gone and its history is durable.
        self.ds.sched.node2pending[node] = [pending['source']['index']]
        node.send_runtest_some([pending['source']['index']])
        node.shutdown()

    def permit(self, node, channel, message):
        pending = self.reserved.get(node.gateway.id)
        if pending is None:
            return False
        name = node.gateway.id
        if (set(message) != {'sequence', 'index', 'slot'} or type(message['sequence']) is not int
                or message['sequence'] != self.pool.sequences.get(name, 0) + 1
                or message['index'] != pending['source']['index']):
            raise ValueError('Invalid move target reservation')
        self.pool.sequences[name] = message['sequence']
        if message['slot'] is None:
            channel.send(dict(sequence=message['sequence'], allowed=self.pending is pending, token=None))
        else:
            if type(message['slot']) is not int or not 0 <= message['slot'] < self.pool.rows[name]['budget']:
                raise ValueError('Invalid move target lease')
            if self.pending is not pending:
                channel.send(dict(sequence=message['sequence'], allowed=False, token=None))
            else:
                source = self.current.get(pending['source']['worker'])
                if (source is None or source['token'] != pending['attempt'] or source['state'] != 'running'
                        or self.pool.owner.desired[pending['target']] == 0):
                    self.reject(pending, 'Source finished or target disabled before reservation')
                    self.pending = None
                    self.pool.retiring.add(name)
                    channel.send(dict(sequence=message['sequence'], allowed=False, token=None))
                    return True
                pending.update(state='cancelling', channel=channel, sequence=message['sequence'], slot=message['slot'])
                pending['deadline'] = time.monotonic() + 30
                pending['future'] = self.executor.submit(self.cancel_remote, pending['source'])
        return True

    def cancel_remote(self, active):
        from .attempt_transport import cancel_remote
        return cancel_remote(active, self.ready, self.pool.rows,
                             self.pool.config._sr_host_profile, self.ds.nodemanager.group)

    def errordown(self, node, error):
        pending = self.pending
        if pending is not None and pending['source']['worker'] == node.gateway.id and pending['state'] == 'cancelling':
            self.deferred[node.gateway.id] = (node, error)
            return True
        return False

    def advance(self):
        p = self.pending
        if p is None:
            return
        if time.monotonic() > p['deadline']:
            if p['state'] == 'cancelling':
                self.fail('Move confirmation timed out')
            else:
                self.reject(p, 'Target reservation timed out; source continues')
                self.deny_target(p)
                self.pending = None
            return
        if p['state'] == 'draining_target':
            if p['old_target'] is None or p['old_target'] not in self.ds._active_nodes:
                self.spawn_target(p)
        elif p['state'] == 'cancelling' and p['future'].done():
            try:
                receipt = p['future'].result()
                if not receipt.get('cancelled'):
                    self.reject(p, receipt.get('reason', 'Attempt already finished'))
                    self.deny_target(p)
                    self.pending = None
                    return
                if self.ds.shuttingdown or self.ds.shouldstop or self.pool.owner.desired[p['target']] == 0:
                    raise ValueError('Gate stopped or target disabled during cancellation')
                source = p['source']
                name = source['worker']
                server = next(s for s in self.pool.config._sr_pool_servers if s.worker == name)
                if name not in self.deferred or not server.closed.is_set():
                    return  # bounded by deadline; no restart without both proofs
                if (receipt.get('children_remaining') != 0 or receipt['attempt']['token'] != source['token']
                        or any(receipt['attempt'][k] != source[k] for k in ('index', 'nodeid', 'slot', 'start'))):
                    raise ValueError('Cancellation acknowledgement differs from the exact attempt')
                state = self.pool.config._specroad_verification
                phases = self.pool.config._sr_pool_history.cancel(state.history_run, source['nodeid'],
                    self.pool.config._sr_host_profile['selected'][source['nodeid']], name, p['worker'],
                    source['token'], json.dumps(receipt, sort_keys=True))
                state.ledger.cancel(source['nodeid'], name, source['token'], phases)
                self.cancelled[name] = dict(receipt=receipt, target=p['worker'], token=source['token'])
                proof = dict(self.ready[name]['proof'])
                proof['leases'] = [{k: a[k] for k in ('nodeid', 'slot', 'start', 'end', 'token')}
                                   for a in receipt['completed']]
                proof['leases'].append({k: receipt['attempt'][k] for k in ('nodeid', 'slot', 'start', 'end', 'token')} | {'cancelled': True})
                self.pool.config._sr_pool_outputs[name] = proof
                node, _ = self.deferred.pop(name)
                self.ds.sched.remove_cancelled(node, source['index'])
                self.ds._active_nodes.remove(node)
                self.pool.active.pop(name, None)
                self.current.pop(name, None)
                token = self.granted(p['worker'], source['index'], p['slot'])
                self.pool.active[p['worker']] = source['index']
                self.pool.grants.setdefault(p['worker'], []).append(dict(index=source['index'], slot=p['slot'], token=token))
                p['channel'].send(dict(sequence=p['sequence'], allowed=True, token=token))
                self.receipts[p['id']] = {k: p[k] for k in ('id', 'attempt', 'target')} | dict(state='restarted', worker=p['worker'], next_attempt=token)
                del self.reserved[p['worker']]
                self.pending = None
            except Exception as error:
                source = self.current.get(p['source']['worker'])
                if (p['source']['worker'] not in self.deferred and (source is None or source['token'] != p['attempt'])):
                    self.reject(p, 'Source completed while the operator request was in transit')
                    self.deny_target(p)
                    self.pending = None
                else:
                    self.fail(str(error))

    def deny_target(self, pending):
        if 'channel' in pending:
            try:
                pending['channel'].send(dict(sequence=pending['sequence'], allowed=False, token=None))
            except OSError:
                self.pool.errors.append('Move target acknowledgement channel lost')
        if 'worker' in pending:
            self.pool.retiring.add(pending['worker'])

    def fail(self, reason):
        pending = self.pending
        self.reject(pending, reason)
        self.deny_target(pending)
        self.pool.errors.append('Move failed: ' + reason)
        self.ds.shouldstop = 'Move could not prove safe cancellation and restart'
        self.pending = None
        for name, (node, error) in list(self.deferred.items()):
            del self.deferred[name]
            self.pool.native_errordown(node, error)

    def close(self):
        self.executor.shutdown(wait=True)
