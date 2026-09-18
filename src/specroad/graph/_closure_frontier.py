"""Deterministic identity worklist, separated from closure's dependency rules.

It owns pending/visited identities and processing order. Future resumable work
services can bind that state at this boundary; this is not a durable checkpoint
or a scheduler for development tests.
"""
import heapq


class IdentityFrontier:
    def __init__(self, initial):
        self._pending = set()
        self._visited = set()
        self._order = []
        self._heap = []
        self.extend(initial)

    def __bool__(self):
        return bool(self._pending)

    def extend(self, nodes):
        for node in nodes:
            if node not in self._visited and node not in self._pending:
                self._pending.add(node)
                heapq.heappush(self._heap, (node.order_key, node))

    def take(self):
        _, node = heapq.heappop(self._heap)
        self._pending.remove(node)
        self._visited.add(node)
        self._order.append(node)
        return node

    @property
    def visited(self):
        return frozenset(self._visited)

    @property
    def processing_order(self):
        return tuple(self._order)
