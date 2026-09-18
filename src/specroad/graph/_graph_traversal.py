"""Shared iterative DFS for all protected relation hierarchies.

The caller supplies already resolved edges for one relation kind. A witness
is deterministic for the same logical input; this is not a scope resolver.
"""

def _cycle_witness(edges):
    """Find one deterministic directed cycle without recursive Python frames."""
    outgoing = {}
    for edge in edges:
        outgoing.setdefault(edge.source.id, []).append(edge)
        outgoing.setdefault(edge.target.id, [])
    for values in outgoing.values():
        values.sort(key=lambda edge: (edge.target.id, edge.relation.identity.id))
    finished = set()
    for root in sorted(outgoing):
        if root in finished:
            continue
        active = {root: 0}
        nodes = [root]
        path = []
        frames = [iter(outgoing[root])]
        while frames:
            edge = next(frames[-1], None)
            if edge is None:
                finished_node = nodes.pop()
                finished.add(finished_node)
                del active[finished_node]
                frames.pop()
                if path:
                    path.pop()
                continue
            target = edge.target.id
            if target in active:
                cycle = path[active[target]:] + [edge]
                first = min(range(len(cycle)), key=lambda index: cycle[index].source.id)
                return tuple(cycle[first:] + cycle[:first])
            if target not in finished:
                active[target] = len(nodes)
                nodes.append(target)
                path.append(edge)
                frames.append(iter(outgoing[target]))
    return None

