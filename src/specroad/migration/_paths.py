"""Pure DAG topology, bounded path counting and reachability; no providers."""
from collections import deque

from .contracts import MigrationError


def _topological(nodes, edges):
    degree = dict.fromkeys(nodes, 0)
    for rows in edges.values():
        for row in rows:
            degree[row.target] += 1
    pending = deque(node for node in nodes if degree[node] == 0)
    ordered = []
    while pending:
        node = pending.popleft()
        ordered.append(node)
        for row in edges[node]:
            degree[row.target] -= 1
            if degree[row.target] == 0:
                pending.append(row.target)
    if len(ordered) != len(nodes):
        raise MigrationError('cycle')
    return tuple(ordered)


def _paths(source, target, edges, order):
    """Count DAG paths in O(V+E), saturating at two; keep one predecessor."""
    counts, previous = {source: 1}, {}
    for node in order:
        count = counts.get(node, 0)
        if count:
            for edge in edges[node]:
                counts[edge.target] = min(2, counts.get(edge.target, 0) + count)
                previous[edge.target] = edge
    count = counts.get(target, 0)
    if count > 1:
        raise MigrationError('ambiguous_path')
    if not count:
        return None
    path, node = [], target
    while node != source:
        edge = previous[node]
        path.append(edge)
        node = edge.source
    return tuple(reversed(path))


def _reachable(source, target, edges):
    """Direction diagnostic only: ambiguity in an unavailable inverse is irrelevant."""
    pending, seen = [source], {source}
    while pending:
        node = pending.pop()
        if node == target:
            return True
        for edge in edges[node]:
            if edge.target not in seen:
                seen.add(edge.target)
                pending.append(edge.target)
    return False
