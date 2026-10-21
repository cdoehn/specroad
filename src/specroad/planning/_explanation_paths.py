"""Private explanation traversal using shared shortest-path and identity values.

Callers validate the supplied project scope first. The Roadmap link policy
owns membership/origin eligibility; neighbor paths remain stored observations,
without reusing Why's different edge policy or expanding Release scope.
"""
from collections import deque

from ..graph._shortest_search import discover_predecessor
from ..graph.path_output import PathRecord, _path_identity_key


def _context_edge(view):
    if not view.inverse:
        return view.type in ('addresses', 'refines', 'derived_from')
    return ((view.type == 'implemented_by' and view.source.artifact_type == 'task') or
            (view.type == 'scheduled_for' and view.source.artifact_type in ('release', 'milestone')) or
            (view.type == 'part_of' and view.source.artifact_type == 'release'
             and view.target.artifact_type == 'milestone'))


def _context_paths(index, start, depth):
    """All shortest paths under the explicit explanation link policy."""
    distances, predecessors = {start: 0}, {start: []}
    pending = deque([start])
    while pending:
        current = pending.popleft()
        if distances[current] == depth:
            continue
        for view in index.for_artifact(current):
            if _context_edge(view) and discover_predecessor(
                    distances, predecessors, current, view.target.id, view, keep_equal=True):
                pending.append(view.target.id)
    identities = {value.id: value for value in index.references.sources}
    paths = []
    for target in sorted(distances):
        # Iterate the predecessor DAG without a recursive Python depth limit.
        stack = [(target, ())]
        while stack:
            current, reverse = stack.pop()
            if current == start:
                paths.append(PathRecord.from_views(identities[start], tuple(reversed(reverse))))
            else:
                for view in reversed(predecessors[current]):
                    stack.append((view.source.id, (*reverse, view)))
    return paths


def _explanation_paths(index, artifact_id, depth):
    """Keep all shortest context paths and the separately typed direct neighbors."""
    context = _context_paths(index, artifact_id, depth)
    paths = [('context', path) for path in context]
    for path in context:
        if len(path.relations) >= depth:
            continue
        for view in index.for_artifact(path.artifacts[-1].id, direction='outgoing'):
            purpose = {'scheduled_for': 'assignment', 'depends_on': 'dependency',
                       'mitigates': 'risk'}.get(view.type)
            if view.type == 'part_of' and view.source.artifact_type in ('task', 'milestone'):
                purpose = 'parent'
            if purpose is None or view.target.id in {a.id for a in path.artifacts}:
                continue
            extended = PathRecord((*path.artifacts, view.target),
                                  (*path.relations, view.stored.relation.identity), (*path.inverse, False))
            paths.append((purpose, extended))
            if (purpose == 'assignment' and view.target.artifact_type == 'milestone'
                    and len(extended.relations) < depth):
                for parent in index.for_artifact(view.target.id, direction='outgoing'):
                    if parent.type == 'part_of' and parent.target.id not in {a.id for a in extended.artifacts}:
                        paths.append((purpose, PathRecord((*extended.artifacts, parent.target),
                            (*extended.relations, parent.stored.relation.identity), (*extended.inverse, False))))
    paths = sorted(set(paths), key=lambda row: (row[0], *_path_identity_key(row[1])))
    return context, paths
