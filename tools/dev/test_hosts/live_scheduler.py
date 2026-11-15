"""Duration scheduling plus explicit drain accounting, without operator IO."""
from .scheduler import HostScheduling


class LiveScheduling(HostScheduling):
    def __init__(self, config, log=None):
        super().__init__(config, log)
        self.control = config._sr_live_pool
        self.reclaimed = {}

    def host(self, node):
        return self.control.rows[node.gateway.id]

    def scheduling_nodes(self):
        return [n for n in self.nodes if self.control.eligible(n) and n in self.node2collection]

    @property
    def tests_finished(self):
        return (self.collection is not None and not self.has_pending
                and not getattr(self.control.moves, 'busy', False))

    def check_schedule(self):
        self.control.reconcile()
        if self.release_tail():
            self.control.reconcile()
        super().check_schedule()

    def release_tail(self):
        """Return an unstarted lookahead without touching its running predecessor.

        All dispatch and permission events run on the controller's main loop.
        A prefetched item is not executable without a fresh, per-item permit.
        Revoke that permit before exposing the item to another worker. The old
        worker finishes its current protocol with native fixture semantics and
        exits on the denied next permit (or confirmed speculative cancellation).
        """
        pool, moves = self.control, self.control.moves
        if (not self.ready or self.pending or not getattr(moves, 'speculative', False)
                or not moves.waiting() or moves.pending is not None
                or pool.ds.shuttingdown or pool.ds.shouldstop):
            return False
        # Count actual processes, including draining/collecting workers. A
        # revoked tail must not merely move behind a lease held by its donor.
        spare = any(wanted > sum(pool.rows[n.gateway.id]['host'] == host
                                  for n in pool.ds._active_nodes)
                    for host, wanted in pool.owner.desired.items())
        idle = any(not self.node2pending[n] and pool.owner.desired[self.host(n)['host']] > 0
                   for n in self.scheduling_nodes())
        if not (spare or idle):
            return False
        for node in sorted(self.nodes, key=lambda n: n.gateway.id):
            name = node.gateway.id
            queue = self.node2pending[node]
            current = moves.current.get(name, {})
            if (node not in pool.ds._active_nodes or name in self.reclaimed
                    or name in moves.reserved or name in moves.copies or name in moves.killing
                    or len(queue) < 2 or pool.active.get(name) != queue[0]
                    or current.get('state') != 'running'):
                continue
            tail = tuple(queue[1:])
            if any(i in moves.begun or i in self.remaining or i in self.pending for i in tail):
                raise ValueError('Tail reservation is already started or returned')
            self.reclaimed[name] = tail
            pool.retiring.add(name)
            self.node2pending[node] = queue[:1]
            self._queue_unstarted(tail)
            node.shutdown()
            return True
        return False

    def denies_reclaimed(self, node, index):
        name = node.gateway.id
        if index not in self.reclaimed.get(name, ()):
            return False
        if name not in self.control.retiring or name in self.control.active or self.node2pending[node]:
            raise ValueError('Reclaimed successor requested before predecessor completion')
        return True

    def add_node_collection(self, node, collection):
        super().add_node_collection(node, collection)
        if self.control.moves is not None:
            self.control.moves.collection(node)

    def mark_test_complete(self, node, item_index, duration=None):
        if self.control.moves is not None:
            token = self.control.moves.current[node.gateway.id]['token']
            self.control.moves.finished(node.gateway.id, item_index)
        if self.control.active.pop(node.gateway.id, None) != item_index:
            raise ValueError('Completed test lacks its live permission')
        super().mark_test_complete(node, item_index, duration)
        if self.control.moves is not None:
            self.control.control_channels[node.gateway.id].send(dict(completed=token))

    def remove_cancelled(self, node, index):
        reserved = self.node2pending[node]
        if not reserved or reserved[0] != index:
            raise ValueError('Cancelled index no longer belongs to its source worker')
        self.node2pending[node] = reserved[1:]
        self._return_unstarted(node)

    def _return_unstarted(self, node):
        reserved = self.node2pending.pop(node)
        self.started.pop(node, None)
        self.reclaimed.pop(node.gateway.id, None)
        self._queue_unstarted(reserved)

    def _queue_unstarted(self, reserved):
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

    def remove_node(self, node):
        name = node.gateway.id
        if self.control.moves is not None and (name in self.control.moves.reserved
                or name in getattr(self.control.moves, 'copies', {})):
            self.node2pending.pop(node, None)
            self.started.pop(node, None)
            self.reclaimed.pop(name, None)
            return None
        if name in self.control.retiring and name not in self.control.active and getattr(node, 'workeroutput', {}).get('exitstatus') == 0:
            self._return_unstarted(node)
            self.check_schedule()
            return None
        self.reclaimed.pop(name, None)
        return super().remove_node(node)
