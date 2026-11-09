"""Duration-aware xdist dispatch with short queues and heterogeneous host estimates."""
import heapq
import math
import time

from xdist.scheduler.worksteal import WorkStealingScheduling


class HostScheduling(WorkStealingScheduling):
    def __init__(self, config, log=None):
        super().__init__(config, log)
        self.profile = config._sr_host_profile
        self.started = {}
        self.scale = {}
        self.ready = False

    def host(self, node):
        return self.profile['workers'][node.gateway.id]

    def identity(self, index):
        return self.profile['selected'][self.collection[index]]

    def speed(self, node):
        host = self.host(node)
        return host['speed'] / self.scale.get(host['host'], 1.0)

    def duration(self, node, index):
        host = self.host(node)
        identity = self.identity(index)
        measured = self.profile['estimates'].get(identity + '\n' + host['host'])
        forecast = measured if measured is not None else self.profile['baseline'].get(identity, 300.0) / host['speed']
        return max(0.001, forecast * self.scale.get(host['host'], 1.0))

    def available(self, node):
        queue = self.node2pending[node]
        if not queue:
            return 0.0
        first = self.duration(node, queue[0])
        elapsed = time.monotonic() - self.started.get(node, time.monotonic())
        # An overrun has unknown remaining time, not an invented zero.
        return max(first * 0.2, first - elapsed) + sum(self.duration(node, i) for i in queue[1:])

    def candidates(self, heap, count=24):
        result, held = [], []
        while heap and len(result) < count:
            value, index = heapq.heappop(heap)
            if index in self.remaining:
                result.append(index)
                held.append((value, index))
        for item in held:
            heapq.heappush(heap, item)
        return result

    def pool_horizon(self, live):
        """Estimate the whole remaining run, not the fastest next free slot."""
        loads = [(self.available(node), self.speed(node)) for node in live
                 if not node.shutting_down]
        capacity = math.fsum(speed for _, speed in loads)
        work = self.remaining_work + math.fsum(delay * speed for delay, speed in loads)
        return max(max(delay for delay, _ in loads), work / capacity)

    def short_successor(self, node, live):
        # A real nextitem lets xdist execute the current item. A faster host's
        # existence does not justify retiring this worker for the entire run.
        # Unknowns are never used as speculative filler on a weaker host.
        horizon = self.pool_horizon(live)
        delay = self.available(node)
        for index in self.candidates(self.short, 12):
            if delay + self.duration(node, index) <= horizon + 0.001:
                return index
        return None

    def check_schedule(self):
        if self.collection is None:
            return
        if not self.ready:
            self.remaining = set(self.pending)
            self.unknown = [i for i in self.pending if self.identity(i) not in self.profile['baseline']]
            unknown_set = set(self.unknown)
            known = [i for i in self.pending if i not in unknown_set]
            self.long = [(-self.profile['baseline'][self.identity(i)], i) for i in known]
            self.short = [(-value, i) for value, i in self.long]
            heapq.heapify(self.long)
            heapq.heapify(self.short)
            reference = max(self.nodes, key=self.speed)
            # Freeze normalized work once. Host-specific measurements take
            # precedence; online host scales change capacity, not this ledger.
            self.work_weights = {i: self.duration(reference, i) * self.speed(reference)
                                 for i in self.pending}
            self.remaining_work = math.fsum(self.work_weights.values())
            self.ready = True
        live = [n for n in self.nodes if not n.shutting_down]
        if not live:
            return
        live.sort(key=lambda n: (-self.speed(n), n.gateway.id))
        fastest = self.speed(live[0])
        exploration = max(1, math.ceil(sum(self.speed(n) == fastest for n in live) / 4))
        # Each worker needs a nextitem to execute its current item. Assign in
        # two rounds, so the fastest worker does not reserve all long tests.
        for depth in (0, 1):
            for position, node in enumerate(live):
                queue = self.node2pending[node]
                if node.shutting_down or len(queue) > depth:
                    continue
                while self.unknown and self.unknown[-1] not in self.remaining:
                    self.unknown.pop()
                candidates = self.candidates(self.long)
                # Limited fast slots explore unknowns early. A known long test
                # can still occupy the second position and other fast slots.
                if self.unknown and ((position < exploration and depth == 0) or (not candidates and self.speed(node) == fastest)):
                    candidates.insert(0, self.unknown[-1])
                candidates += self.candidates(self.short, 12)
                chosen = None
                for index in dict.fromkeys(candidates):
                    finish = self.available(node) + self.duration(node, index)
                    earliest = min(self.available(other) + self.duration(other, index) for other in live if not other.shutting_down)
                    if finish <= earliest * 1.05 + 0.001:
                        chosen = index
                        break
                if chosen is None and len(queue) == 1:
                    faster = any(not other.shutting_down and self.speed(other) > self.speed(node) for other in live)
                    chosen = self.short_successor(node, live)
                    if chosen is None and not faster:
                        # At least one fastest worker must keep making
                        # progress even when the estimates cannot fit a pair.
                        short = self.candidates(self.short, 1)
                        if short:
                            chosen = short[0]
                        elif self.unknown:
                            chosen = self.unknown[-1]
                    if chosen is None:
                        node.shutdown()
                        continue
                if chosen is not None:
                    self.remaining.remove(chosen)
                    self.pending.remove(chosen)
                    self.remaining_work = max(0.0, self.remaining_work - self.work_weights[chosen])
                    if not queue:
                        self.started[node] = time.monotonic()
                    queue.append(chosen)
                    node.send_runtest_some([chosen])
        if not self.pending:
            for node in live:
                if len(self.node2pending[node]) < 2 and not node.shutting_down:
                    node.shutdown()

    def mark_test_complete(self, node, item_index, duration=None):
        expected = self.duration(node, item_index)
        if duration is not None and duration > 0:
            name = self.host(node)['host']
            old = self.scale.get(name, 1.0)
            self.scale[name] = min(20.0, max(0.05, old * (0.8 + 0.2 * min(4.0, max(0.25, duration / expected)))))
        self.node2pending[node].remove(item_index)
        self.started[node] = time.monotonic()
        self.check_schedule()

    def remove_node(self, node):
        pending = self.node2pending.pop(node)
        self.started.pop(node, None)
        # No re-execution or manufactured success after loss. The gate fails;
        # a new bound Apply correction owns any subsequent attempt.
        crash = self.collection[pending[0]] if pending and self.collection else None
        self.check_schedule()
        return crash
