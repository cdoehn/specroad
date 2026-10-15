"""Private cooperative breadth-first predecessor search for Why.

The owning traversal retains these fields in its shared checkpoint state.
Only this search advances distances, predecessors and the adjacency frontier.
"""
from .symmetry import SYMMETRIC_RELATION_TYPES
from ._shortest_search import discover_predecessor


def _token(view):
    return [view.relation_id, view.inverse]


class _WhySearch:
    def _search_step(self):
        if self._current is None:
            current = self._pending.popleft()
            if self._distances[current] < self._depth:
                views = self._index.for_artifact(current)
                if views:
                    self._current, self._current_views = current, views
        else:
            view = self._current_views[self._edge_offset]
            if not view.inverse or view.type in SYMMETRIC_RELATION_TYPES:
                target = view.target.id
                if discover_predecessor(self._distances, self._predecessors,
                                        self._current, target, _token(view), keep_equal=True):
                    self._pending.append(target)
            self._edge_offset += 1
            if self._edge_offset == len(self._current_views):
                self._current, self._current_views, self._edge_offset = None, (), 0
        if not self._pending and self._current is None:
            self._targets = self._ordered_targets()
            self._phase = 'paths' if self._targets else 'complete'
            if self._targets:
                self._frames = [{'node': self._targets[0], 'next_predecessor': 0}]

    def _ordered_targets(self):
        return sorted((name for name in self._distances
                       if self._identities[name].artifact_type in ('goal', 'need', 'source')),
                      key=lambda name: (self._identities[name].artifact_type, name))
