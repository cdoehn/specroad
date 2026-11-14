"""Duration scheduling plus explicit drain accounting, without operator IO."""
from .scheduler import HostScheduling


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
        if self.control.moves is not None and name in self.control.moves.reserved:
            self.node2pending.pop(node, None)
            self.started.pop(node, None)
            return None
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
