"""Private cooperative trace frontier; supplied immutable graph, no project I/O."""
from dataclasses import dataclass, field

from ._closure_frontier import IdentityFrontier
from .indices import RelationIndex


@dataclass(frozen=True)
class _TraceNode:
    identifier: str
    distance: int = field(compare=False)

    @property
    def order_key(self):
        # Unit edge lengths: the first admitted identity has minimum distance.
        return self.distance, self.identifier


class _TraceFrontier:
    """Cooperative traversal of an immutable supplied index, without I/O.

    One work unit visits one node or consumes one of its directed edge views.
    The live object retains the frontier and an unfinished adjacency cursor.
    This is process-local continuation, not a serializable Work checkpoint.
    """

    def __init__(self, index, artifact_id, *, direction, depth):
        if type(index) is not RelationIndex:
            raise TypeError('Trace requires a resolved RelationIndex.')
        if (type(direction) is not str or direction not in ('in', 'out', 'both')
                or type(depth) is not int or depth < 0):
            raise ValueError('Trace requires a direction and nonnegative integer depth.')
        self._selected_direction = {'in': 'incoming', 'out': 'outgoing', 'both': 'both'}[direction]
        index.for_artifact(artifact_id, direction=self._selected_direction)
        self._index = index
        self._start, self._direction, self._depth = artifact_id, direction, depth
        self._identities = {identity.id: identity for identity in index.references.sources}
        initial = _TraceNode(artifact_id, 0)
        self._frontier = IdentityFrontier((initial,))
        self._admitted = {artifact_id: initial}
        self._nodes, self._views = [], {}
        self._current, self._current_views, self._edge_offset = None, (), 0
        self._units = 0
        self._complete = self._closed = self._failed = False

    @property
    def state(self):
        visited = self._frontier.visited
        pending = sorted((node for node in self._admitted.values() if node not in visited),
                         key=lambda node: node.order_key)
        current = self._current
        return {'format_version': 'trace-traversal-cursor-v1',
                'phase': ('failed' if self._failed else 'complete' if self._complete
                          else 'cancelled' if self._closed else 'traversing'),
                'start': self._start, 'direction': self._direction, 'depth': self._depth,
                'complete': self._complete, 'units_completed': self._units,
                'pending': [{'id': node.identifier, 'distance': node.distance} for node in pending],
                'current': None if current is None else {
                    'id': current.identifier, 'distance': current.distance,
                    'next_edge': self._edge_offset,
                    'remaining_edges': len(self._current_views) - self._edge_offset},
                'visited_count': len(self._nodes), 'edge_view_count': len(self._views),
                'validation_scope': 'supplied_relation_set_only', 'durable_checkpoint': False}

    def advance(self, units):
        if type(units) is not int or units <= 0:
            raise ValueError('Trace work units must be a positive integer.')
        if self._closed or self._failed:
            raise RuntimeError('Trace traversal is not available.')
        try:
            for _ in range(units):
                if self._complete:
                    break
                if self._current is None:
                    node = self._frontier.take()
                    self._nodes.append(node)
                    if node.distance < self._depth:
                        views = self._index.for_artifact(node.identifier, direction=self._selected_direction)
                        if views:
                            self._current, self._current_views = node, views
                else:
                    view = self._current_views[self._edge_offset]
                    self._views[(view.relation_id, view.inverse)] = view
                    target = _TraceNode(view.target.id, self._current.distance + 1)
                    self._admitted.setdefault(target.identifier, target)
                    self._frontier.extend((target,))
                    self._edge_offset += 1
                    if self._edge_offset == len(self._current_views):
                        self._current, self._current_views, self._edge_offset = None, (), 0
                self._units += 1
                self._complete = self._current is None and not self._frontier
        except Exception:
            self._failed = True
            raise
        return self._complete

    @property
    def result(self):
        if not self._complete or self._closed or self._failed:
            raise RuntimeError('A complete open trace traversal is required.')
        nodes = [{'id': node.identifier, 'artifact_type': self._identities[node.identifier].artifact_type,
                  'distance': node.distance} for node in self._nodes]
        ordered = sorted(self._views.values(), key=lambda view: (
            view.source.id, view.type, view.target.id, view.relation_id, view.inverse))
        edges = [{'relation_id': view.relation_id, 'type': view.type,
                  'source': view.source.id, 'target': view.target.id, 'inverse': view.inverse,
                  'stored_source': view.stored.source.id, 'stored_relation': view.stored.relation.data}
                 for view in ordered]
        return {'nodes': nodes, 'edges': edges}

    def close(self):
        self._closed = True
