"""Confirmed process cleanup, independent of scheduling and copy selection."""
import json
import time


class CopyCleanup:
    def kill(self, row):
        name = row['worker']
        if name not in self.killing:
            self.pool.retiring.add(name)
            self.killing[name] = dict(source=row.copy(), deadline=time.monotonic()+30,
                                     future=self.executor.submit(self.cancel_remote, row.copy()))

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
        try:
            receipt = job['future'].result()
        except Exception:
            # A normally completed worker can close its endpoint before the
            # cancel RPC arrives. Only its actual matching native output can
            # settle that race; absence of a process is never an acknowledgement.
            record = self.state.ledger.attempts.get((source['nodeid'], name), {})
            if record.get('state') != 'complete' or name in self.deferred:
                raise
            output = self.pool.config._sr_pool_outputs.get(name)
            if output is None:
                return
            if (any(output.get(k) != self.ready[name]['proof'][k]
                    for k in ('source_sha256','snapshot_sha256','environment_sha256','account','host'))
                    or not any(all(a.get(k) == source[k] for k in ('token','nodeid','slot','start'))
                               for a in output.get('leases', []))):
                raise ValueError('Natural loser completion lacks its bound worker proof')
            del self.killing[name]
            return
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

    def reap_pending(self):
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
