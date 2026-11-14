"""Explicit move lifecycle on xdist's controller thread, never automatic retries."""
from concurrent.futures import ThreadPoolExecutor
import json
import time
import uuid

import execnet

from dev.test_control.moves import requests
from .attempt_supervisor import request


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

    def granted(self, name, index, slot):
        token = uuid.uuid4().hex
        self.current[name] = dict(token=token, index=index, slot=slot, worker=name,
            nodeid=self.ds.sched.collection[index], host=self.pool.rows[name]['host'], state='starting')
        return token

    def signal(self, node, channel, message):
        name = node.gateway.id
        if (type(message) is not dict or set(message) != {'sequence', 'kind', 'value'}
                or type(message['sequence']) is not int
                or message['sequence'] != self.pool.sequences.get(name, 0) + 1):
            raise ValueError('Invalid attempt event sequence')
        self.pool.sequences[name] = message['sequence']
        kind, value = message['kind'], message['value']
        if kind == 'ready':
            if name in self.ready or type(value) is not dict or set(value) != {'endpoint', 'secret', 'proof'}:
                raise ValueError('Invalid worker supervisor binding')
            self.ready[name] = value
        elif kind in ('started', 'complete'):
            active = self.current.get(name)
            if active is None or value.get('token') != active['token']:
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
        if self.pending is not None:
            self.advance()
            return
        for row in requests(self.pool.owner.root, self.pool.owner.run)['requests']:
            if row['id'] in self.receipts:
                continue
            self.receipts[row['id']] = {**row, 'state': 'checking'}
            found = next((r for r in self.current.values() if r['token'] == row['attempt'] and r['state'] == 'running'), None)
            if found is None or row['target'] not in self.pool.owner.capacities or self.pool.owner.desired.get(row['target'], 0) == 0:
                self.reject(row, 'Attempt finished or target is no longer enabled')
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
                pending.update(state='cancelling', channel=channel, sequence=message['sequence'], slot=message['slot'])
                pending['future'] = self.executor.submit(self.cancel_remote, pending['source'])
        return True

    def cancel_remote(self, active):
        binding = self.ready[active['worker']]
        row = self.pool.rows[active['worker']]
        spec = execnet.XSpec(row['spec'])
        if spec.via:
            gateway = self.ds.nodemanager.group[spec.via]
            channel = gateway.remote_exec("""import sys
root,endpoint,secret,token=channel.receive()
sys.path.insert(0,root+'/tools')
from dev.test_hosts.attempt_supervisor import request
from dev.test_hosts.environment import environment,digest
from dev.test_hosts.snapshot import inventory,fingerprint
from verification_support.identity import source_identity
reply=request(endpoint,secret,'cancel',token=token)
reply['binding']={'source_sha256':source_identity(root),'snapshot_sha256':fingerprint(inventory(root)),'environment_sha256':digest(environment())}
channel.send(reply)
""")
            channel.send((row['root'], binding['endpoint'], binding['secret'], active['token']))
            reply = channel.receive(timeout=20)
        else:
            from .environment import environment, digest
            from .snapshot import inventory, fingerprint
            from verification_support.identity import source_identity
            reply = request(binding['endpoint'], binding['secret'], 'cancel', token=active['token'])
            reply['binding'] = dict(source_sha256=source_identity(row['root']),
                snapshot_sha256=fingerprint(inventory(row['root'])), environment_sha256=digest(environment()))
        profile = self.pool.config._sr_host_profile
        if reply['binding'] != dict(source_sha256=profile['source_sha256'], snapshot_sha256=profile['snapshot_sha256'], environment_sha256=row['environment_sha256']):
            raise ValueError('Source or environment changed before cancellation confirmation')
        return reply

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
            self.fail('Move confirmation timed out')
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
                self.fail(str(error))

    def deny_target(self, pending):
        if 'channel' in pending:
            pending['channel'].send(dict(sequence=pending['sequence'], allowed=False, token=None))
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
