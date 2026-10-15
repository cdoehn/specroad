"""Shared iterative DFS over resolved directed edges.

Identity accessors also allow configuration-parent edges to use the same
cycle primitive. A witness is deterministic; this is not a scope resolver.
"""

def _cycle_witness(edges, *, source_id=lambda edge: edge.source.id,
                   target_id=lambda edge: edge.target.id,
                   edge_id=lambda edge: edge.relation.identity.id):
    """Find one deterministic directed cycle without recursive Python frames."""
    outgoing = {}
    for edge in edges:
        outgoing.setdefault(source_id(edge), []).append(edge)
        outgoing.setdefault(target_id(edge), [])
    for values in outgoing.values():
        values.sort(key=lambda edge: (target_id(edge), edge_id(edge)))
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
            target = target_id(edge)
            if target in active:
                cycle = path[active[target]:] + [edge]
                first = min(range(len(cycle)), key=lambda index: source_id(cycle[index]))
                return tuple(cycle[first:] + cycle[:first])
            if target not in finished:
                active[target] = len(nodes)
                nodes.append(target)
                path.append(edge)
                frames.append(iter(outgoing[target]))
    return None

