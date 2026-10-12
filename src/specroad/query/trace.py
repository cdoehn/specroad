"""Directed depth-bounded trace over a fresh, complete project observation."""
from dataclasses import dataclass, field

from ..cli.command_errors import CommandUsageError
from ..cli.result_schemas import validate_result_document
from ..cli.results import CommandResult, FailureKind, OperationFailure
from ..diagnostics import Diagnostic, from_model_error
from ..graph._closure_frontier import IdentityFrontier
from ..graph.indices import RelationIndex
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..storage.project import ProjectSource
from ..storage.relation_index import build_project_relation_index
from .show import _preflight, _verify_current


@dataclass(frozen=True)
class _TraceNode:
    identifier: str
    distance: int = field(compare=False)

    @property
    def order_key(self):
        # Unit edge lengths: the first admitted identity has minimum distance.
        return self.distance, self.identifier


class TraceTraversal:
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


def _trace_rows(index, artifact_id, direction, depth):
    traversal = TraceTraversal(index, artifact_id, direction=direction, depth=depth)
    try:
        while not traversal.advance(128):
            pass
        result = traversal.result
        return result['nodes'], result['edges']
    finally:
        traversal.close()


def trace_artifact(root, artifact_id, *, direction, depth):
    """Return visited identities and the views traversed below the chosen depth.

    Depth zero contains just the existing start. Nodes are ordered by minimum
    distance/ID; edge views retain their one original stored relation. A boundary
    node is included but not expanded. No resource setting silently reduces depth.
    This synchronous public API has no durable Work or atomic-snapshot claim.
    """
    project = None
    details = dict(atomic_snapshot=False, full_semantic_validation=False,
                   approval_granted=False, write_authorized=False, recovery_performed=False)
    try:
        if (type(direction) is not str or direction not in ('in', 'out', 'both')
                or type(depth) is not int or depth < 0):
            raise OperationFailure(FailureKind.USAGE, 'Trace requires a direction and nonnegative integer depth.')
        source = ProjectSource(root)
        project = {'project_root': str(source.boundary.root), 'project_id': source.configuration.project_id}
        _preflight(source)
        observed = build_project_relation_index(source)
        nodes, edges = _trace_rows(observed.adjacency, artifact_id, direction, depth)
        payload = {'format_version': '1.0.0', 'start': artifact_id, 'direction': direction,
                   'depth': depth, 'nodes': nodes, 'edges': edges,
                   'coverage': {'scope': 'current_project_artifacts',
                       'source_count': observed.source_count, 'relation_count': observed.relation_count,
                       'observation_sha256': observed.binding.sha256,
                       'validation_scope': 'relation_references_and_canonical_storage_only',
                       'atomic_snapshot': False}}
        _preflight(source)
        _verify_current(source, observed.binding)
        validate_result_document('artifact-trace-v1', payload)
        return CommandResult('trace', result=payload, project=project, details=details)
    except OperationFailure as error:
        return CommandResult.failed('trace', error.kind, project=project,
            diagnostics=(Diagnostic('CORE_' + error.kind.name, 'error', 'preflight', str(error)),),
            details={**error.details, **details})
    except (ModelError, SafetyViolation, OSError) as error:
        if isinstance(error, ModelError):
            changed = {'configuration_changed', 'relation_source_changed',
                       'relation_index_membership_changed', 'relation_index_source_changed',
                       'show_source_changed', 'show_source_disappeared'}
            code = 6 if error.reason in changed else getattr(error, 'exit_code', 3)
            diagnostic = from_model_error(error)
        else:
            code = 7 if isinstance(error, SafetyViolation) else 5
            diagnostic = Diagnostic('CORE_SECURITY' if code == 7 else 'CORE_ENVIRONMENT',
                'error', 'runtime', 'Trace could not safely read its inputs.')
        return CommandResult.failed('trace', FailureKind(code), project=project,
                                    diagnostics=(diagnostic,), details=details)


def trace_command(invocation):
    value = invocation.options['--depth']
    if not value or any(character not in '0123456789' for character in value):
        raise CommandUsageError('Trace depth must be a nonnegative decimal integer')
    try:
        depth = int(value)
    except ValueError as error:
        raise CommandUsageError('Trace depth is not a supported integer') from error
    return trace_artifact(invocation.resolved.project_root, invocation.arguments['id'],
                          direction=invocation.options['--direction'], depth=depth)
