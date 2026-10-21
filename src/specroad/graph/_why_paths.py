"""Private iterative materialization of every shortest Why path.

The completed predecessor graph is read-only in this phase. The owner retains
frames, relation positions and the produced prefix in the same checkpoint.
"""
from .path_output import PathRecord, _path_identity_key as _path_key


class _WhyPaths:
    def _path_step(self):
        if not self._frames:
            target = self._targets[self._target_position]
            self._records.sort(key=_path_key)
            self._rows.append({'id': target, 'artifact_type': self._identities[target].artifact_type,
                               'distance': self._distances[target], 'path_count': len(self._records)})
            self._paths.extend(self._records)
            self._records = []
            self._target_position += 1
            if self._target_position == len(self._targets):
                self._phase = 'complete'
            else:
                self._frames = [{'node': self._targets[self._target_position], 'next_predecessor': 0}]
            return
        frame = self._frames[-1]
        current = frame['node']
        if current == self._start:
            views = tuple(self._views[tuple(token)] for token in reversed(self._reverse_views))
            self._records.append(PathRecord.from_views(self._identities[self._start], views))
        elif frame['next_predecessor'] < len(self._predecessors[current]):
            token = self._predecessors[current][frame['next_predecessor']]
            frame['next_predecessor'] += 1
            self._reverse_views.append(token)
            self._frames.append({'node': self._views[tuple(token)].source.id, 'next_predecessor': 0})
            return
        self._frames.pop()
        if self._reverse_views:
            self._reverse_views.pop()
