"""Cooperative shortest paths and input-bound data checkpoints, without I/O.

The owner persists checkpoint bytes and independently retains their SHA-256.
This codec is not a Work-v1 admission, a persistence service or an authenticity
claim for an arbitrary digest supplied alongside an untrusted checkpoint.
"""
from collections import deque
from copy import deepcopy
from hashlib import sha256
import json

from ..graph._why_search import _WhySearch
from ..graph._why_paths import _WhyPaths, _path_key
from ..graph.hierarchies import validate_hierarchies
from ..graph.indices import RelationIndex
from ..graph.path_output import PathRecord
from ..graph.relation_views import RelationView
from ..graph.symmetry import SYMMETRIC_RELATION_TYPES
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError


_FORMAT = 'why-traversal-checkpoint-v1'
_ALGORITHM = 'all-shortest-origin-paths-v1'


def _require(condition):
    if not condition:
        raise ValueError('Invalid Why checkpoint state.')


class WhyTraversal(_WhySearch, _WhyPaths):
    """Resume one node, edge or path-frame operation per positive work unit.

    Input validation, target/path sorting, checkpoint encoding and final output
    projection are indivisible. The complete graph and path prefix remain in
    memory; an operational unit target never truncates semantic scope.
    """

    def __init__(self, index, artifact_id, *, depth):
        if type(index) is not RelationIndex:
            raise TypeError('Why requires a resolved RelationIndex.')
        if type(depth) is not int or depth < 0:
            raise ValueError('Why requires a nonnegative integer depth.')
        validate_hierarchies(index.references)
        index.for_artifact(artifact_id)
        self._index, self._start, self._depth = index, artifact_id, depth
        self._identities = {value.id: value for value in index.references.sources}
        self._views = {}
        for edge in index.references.relations:
            for inverse in (False, True):
                view = RelationView(edge, inverse=inverse)
                if not inverse or view.type in SYMMETRIC_RELATION_TYPES:
                    self._views[(view.relation_id, inverse)] = view
        graph = {'identities': [vars(value) for value in index.references.sources],
                 'relations': [{'source': edge.source.id, 'target': edge.target.id,
                                'data': edge.relation.data} for edge in index.references.relations]}
        self._input_sha256 = sha256(canonical_json_bytes(graph)).hexdigest()
        self._distances, self._predecessors = {artifact_id: 0}, {artifact_id: []}
        self._pending = deque([artifact_id])
        self._current, self._current_views, self._edge_offset = None, (), 0
        self._targets, self._target_position = [], 0
        self._frames, self._reverse_views, self._records = [], [], []
        self._rows, self._paths = [], []
        self._phase, self._units = 'search', 0
        self._closed = self._failed = False

    def advance(self, units):
        if type(units) is not int or units <= 0:
            raise ValueError('Why work units must be a positive integer.')
        self._require_open()
        try:
            for _ in range(units):
                if self._phase == 'complete':
                    break
                if self._phase == 'search':
                    self._search_step()
                else:
                    self._path_step()
                self._units += 1
        except Exception:
            self._failed = True
            raise
        return self._phase == 'complete'

    def _require_open(self):
        if self._closed or self._failed:
            raise RuntimeError('Why traversal is not available.')

    @property
    def state(self):
        return {'phase': 'failed' if self._failed else 'cancelled' if self._closed else self._phase,
                'complete': self._phase == 'complete' and not self._closed and not self._failed,
                'start': self._start, 'depth': self._depth, 'units_completed': self._units,
                'pending': list(self._pending), 'current': self._current,
                'next_edge': self._edge_offset, 'target_position': self._target_position,
                'path_frames': deepcopy(self._frames),
                'paths_materialized': len(self._paths) + len(self._records),
                'checkpoint_format': _FORMAT, 'durable_checkpoint': False,
                'validation_scope': 'supplied_relation_set_and_hierarchies_only'}

    @property
    def result(self):
        self._require_open()
        if self._phase != 'complete':
            raise RuntimeError('A complete Why traversal is required.')
        return {'targets': deepcopy(self._rows), 'paths': [record.as_dict() for record in self._paths]}

    def close(self):
        self._closed = True

    def checkpoint(self):
        """Return owned canonical bytes; the caller owns persistence and trust."""
        self._require_open()
        return canonical_json_bytes({
            'format': _FORMAT, 'algorithm': _ALGORITHM, 'input_sha256': self._input_sha256,
            'start': self._start, 'depth': self._depth, 'phase': self._phase, 'units': self._units,
            'distances': self._distances, 'predecessors': self._predecessors,
            'pending': list(self._pending), 'current': self._current, 'edge_offset': self._edge_offset,
            'targets': self._targets, 'target_position': self._target_position,
            'frames': self._frames, 'reverse_views': self._reverse_views,
            'target_records': [record.as_dict() for record in self._records],
            'rows': self._rows, 'paths': [record.as_dict() for record in self._paths]})

    @classmethod
    def restore(cls, index, raw, *, expected_sha256):
        """Restore a trusted digest's exact state, without replaying its prefix.

        Never derive expected_sha256 from checkpoint data received for import.
        The digest must be independently retained by the checkpoint's owner.
        """
        if (type(raw) is not bytes or type(expected_sha256) is not str
                or len(expected_sha256) != 64
                or any(c not in '0123456789abcdef' for c in expected_sha256)
                or sha256(raw).hexdigest() != expected_sha256):
            raise ValueError('Why checkpoint integrity mismatch.')
        try:
            value = json.loads(raw)
            _require(type(value) is dict and canonical_json_bytes(value) == raw)
            _require(value['format'] == _FORMAT and value['algorithm'] == _ALGORITHM)
            work = cls(index, value['start'], depth=value['depth'])
            _require(set(value) == set(json.loads(work.checkpoint())))
            _require(value['input_sha256'] == work._input_sha256)
            work._restore_state(value)
            _require(work.checkpoint() == raw)
            return work
        except (ValueError, TypeError, KeyError, IndexError, ModelError) as error:
            raise ValueError('Invalid or input-mismatched Why checkpoint.') from error

    def _restore_state(self, value):
        distances, predecessors = value['distances'], value['predecessors']
        _require(type(distances) is dict and type(predecessors) is dict
                 and set(distances) == set(predecessors) and set(distances) <= set(self._identities))
        _require(distances.get(self._start) == 0
                 and all(type(d) is int and 0 <= d <= self._depth for d in distances.values())
                 and all(name == self._start or d > 0 for name, d in distances.items()))
        for name, tokens in predecessors.items():
            _require(type(tokens) is list and bool(tokens) == (name != self._start))
            seen = set()
            for token in tokens:
                view = self._read_view(token)
                _require(tuple(token) not in seen and view.target.id == name
                         and view.source.id in distances
                         and distances[view.source.id] + 1 == distances[name])
                seen.add(tuple(token))
        self._distances, self._predecessors = distances, predecessors
        pending, current, offset = value['pending'], value['current'], value['edge_offset']
        _require(type(pending) is list and all(type(n) is str and n in distances for n in pending)
                 and len(set(pending)) == len(pending)
                 and [distances[n] for n in pending] == sorted(distances[n] for n in pending))
        _require(type(offset) is int and offset >= 0)
        if current is None:
            _require(offset == 0)
        else:
            _require(type(current) is str and current in distances and current not in pending
                     and distances[current] < self._depth
                     and all(distances[current] <= distances[n] for n in pending))
            self._current_views = self._index.for_artifact(current)
            _require(offset < len(self._current_views))
        self._pending, self._current, self._edge_offset = deque(pending), current, offset
        phase, units = value['phase'], value['units']
        _require(type(phase) is str and phase in ('search', 'paths', 'complete')
                 and type(units) is int and units >= 0)
        self._phase, self._units = phase, units
        for field in ('targets', 'frames', 'reverse_views', 'target_records', 'rows', 'paths'):
            _require(type(value[field]) is list)
        position = value['target_position']
        _require(type(position) is int and 0 <= position <= len(value['targets']))
        self._targets, self._target_position = value['targets'], position
        self._frames, self._reverse_views, self._rows = value['frames'], value['reverse_views'], value['rows']
        self._records = [PathRecord.from_dict(item) for item in value['target_records']]
        self._paths = [PathRecord.from_dict(item) for item in value['paths']]
        if phase == 'search':
            _require(bool(pending) or current is not None)
            _require(position == 0 and not any(value[f] for f in
                     ('targets', 'frames', 'reverse_views', 'target_records', 'rows', 'paths')))
            return
        _require(not pending and current is None and self._targets == self._ordered_targets())
        _require(len(self._rows) == position and (position == len(self._targets)) == (phase == 'complete'))
        path_offset = 0
        for target, row in zip(self._targets, self._rows):
            _require(type(row) is dict and type(row.get('path_count')) is int and row['path_count'] > 0
                     and type(row.get('distance')) is int)
            _require(row == {'id': target, 'artifact_type': self._identities[target].artifact_type,
                            'distance': distances[target], 'path_count': row['path_count']})
            records = self._paths[path_offset:path_offset + row['path_count']]
            _require(len(records) == row['path_count'] and records == sorted(records, key=_path_key))
            self._check_records(records, target)
            path_offset += len(records)
        _require(path_offset == len(self._paths))
        if phase == 'complete':
            _require(not self._frames and not self._reverse_views and not self._records)
            return
        target = self._targets[position]
        self._check_records(self._records, target)
        _require(len(self._reverse_views) == max(0, len(self._frames) - 1))
        if not self._frames:
            _require(bool(self._records))
        for i, frame in enumerate(self._frames):
            _require(type(frame) is dict and set(frame) == {'node', 'next_predecessor'})
            node, cursor = frame['node'], frame['next_predecessor']
            _require(type(node) is str and node in distances and type(cursor) is int
                     and 0 <= cursor <= len(predecessors[node]))
            if i == 0:
                _require(node == target)
            else:
                token = self._reverse_views[i - 1]
                view = self._read_view(token)
                previous = self._frames[i - 1]
                _require(view.source.id == node and view.target.id == previous['node']
                         and previous['next_predecessor'] > 0
                         and predecessors[previous['node']][previous['next_predecessor'] - 1] == token)

    def _read_view(self, token):
        _require(type(token) is list and len(token) == 2
                 and type(token[0]) is str and type(token[1]) is bool)
        _require(tuple(token) in self._views)
        return self._views[tuple(token)]

    def _check_records(self, records, target):
        _require(len(set(records)) == len(records))
        for record in records:
            _require(record.artifacts[0] == self._identities[self._start]
                     and record.artifacts[-1] == self._identities[target]
                     and len(record.relations) == self._distances[target])
            for i, (relation, inverse) in enumerate(zip(record.relations, record.inverse)):
                token = [relation.id, inverse]
                view = self._read_view(token)
                _require(view.source == record.artifacts[i] and view.target == record.artifacts[i + 1]
                         and token in self._predecessors[view.target.id])
