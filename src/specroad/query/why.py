"""All shortest directed paths to origins in a fresh complete project observation."""
from collections import deque

from ..cli.result_schemas import validate_result_document
from ..cli.results import CommandResult, FailureKind, OperationFailure
from ..diagnostics import Diagnostic, from_model_error
from ..graph.hierarchies import validate_hierarchies
from ..graph.path_output import PathRecord
from ..graph.symmetry import SYMMETRIC_RELATION_TYPES
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..storage.project import ProjectSource
from ..storage.relation_index import build_project_relation_index
from .show import _preflight, _verify_current


def _why_paths(index, artifact_id, depth):
    index.for_artifact(artifact_id)  # Unknown starts remain errors at depth zero.
    identities = {identity.id: identity for identity in index.references.sources}
    distances, predecessors, pending = {artifact_id: 0}, {artifact_id: []}, deque([artifact_id])
    while pending:
        current = pending.popleft()
        if distances[current] == depth:
            continue
        for view in index.for_artifact(current):
            if view.inverse and view.type not in SYMMETRIC_RELATION_TYPES:
                continue
            target, distance = view.target.id, distances[current] + 1
            if target not in distances:
                distances[target] = distance
                predecessors[target] = []
                pending.append(target)
            if distances[target] == distance:
                predecessors[target].append(view)
    targets = sorted((identities[name] for name in distances
                      if identities[name].artifact_type in ('goal', 'need', 'source')),
                     key=lambda identity: (identity.artifact_type, identity.id))
    rows, paths = [], []
    for target in targets:
        records = []
        stack = [(target.id, ())]
        while stack:
            current, reverse_views = stack.pop()
            if current == artifact_id:
                records.append(PathRecord.from_views(identities[artifact_id], tuple(reversed(reverse_views))))
            else:
                for view in predecessors[current]:
                    stack.append((view.source.id, reverse_views + (view,)))
        records.sort(key=lambda record: (tuple(value.id for value in record.artifacts),
                                        tuple(value.id for value in record.relations), record.inverse))
        rows.append({'id': target.id, 'artifact_type': target.artifact_type,
                     'distance': distances[target.id], 'path_count': len(records)})
        paths.extend(record.as_dict() for record in records)
    return rows, paths


def why_artifact(root, artifact_id):
    """Return every shortest path per reachable Goal, Need and Source.

    Stored directions and symmetric inverse views define connectivity. The
    configured trace_depth is semantic scope; absence is not a guessed default.
    All paths are materialized in this synchronous W implementation.
    """
    project = None
    details = dict(atomic_snapshot=False, full_semantic_validation=False,
                   approval_granted=False, write_authorized=False, recovery_performed=False)
    try:
        source = ProjectSource(root)
        project = {'project_root': str(source.boundary.root), 'project_id': source.configuration.project_id}
        _preflight(source)
        limits = source.configuration.data.get('resource_limits', {})
        if 'trace_depth' not in limits:
            raise ModelError('why_depth_not_configured', path='specroad.json',
                             pointer='/resource_limits/trace_depth')
        depth = limits['trace_depth']
        observed = build_project_relation_index(source)
        validate_hierarchies(observed.adjacency.references)
        targets, paths = _why_paths(observed.adjacency, artifact_id, depth)
        payload = {'format_version': '1.0.0', 'start': artifact_id, 'depth': depth,
                   'traversal': 'stored_direction_with_symmetric_inverses',
                   'targets': targets, 'paths': paths, 'path_count': len(paths),
                   'coverage': {'scope': 'current_project_artifacts',
                       'source_count': observed.source_count, 'relation_count': observed.relation_count,
                       'observation_sha256': observed.binding.sha256,
                       'validation_scope': 'relation_references_canonical_storage_and_hierarchies_only',
                       'atomic_snapshot': False}}
        _preflight(source)
        _verify_current(source, observed.binding)
        validate_result_document('artifact-why-v1', payload)
        return CommandResult('why', result=payload, project=project, details=details)
    except OperationFailure as error:
        return CommandResult.failed('why', error.kind, project=project,
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
                'error', 'runtime', 'Why could not safely read its inputs.')
        return CommandResult.failed('why', FailureKind(code), project=project,
                                    diagnostics=(diagnostic,), details=details)


def why_command(invocation):
    return why_artifact(invocation.resolved.project_root, invocation.arguments['id'])
