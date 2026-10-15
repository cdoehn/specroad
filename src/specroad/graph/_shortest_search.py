"""Shared predecessor discovery for breadth-first searches over unit edges.

Callers own breadth-first order, edge eligibility, queues and path projection.
Only first discovery returns true; equal shortest predecessors may be retained
for all-path materialization or ignored for a canonical first-path result.
"""


def discover_predecessor(distances, predecessors, source, target, edge, *, keep_equal):
    distance = distances[source] + 1
    if target not in distances:
        distances[target] = distance
        predecessors[target] = [edge]
        return True
    if keep_equal and distances[target] == distance:
        predecessors[target].append(edge)
    return False
