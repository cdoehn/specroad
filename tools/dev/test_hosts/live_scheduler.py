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
