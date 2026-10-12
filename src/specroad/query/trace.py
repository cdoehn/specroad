"""Directed depth-bounded trace over a fresh, complete project observation."""
from ..cli.command_errors import CommandUsageError
from ..cli.result_schemas import validate_result_document
from ..cli.results import CommandResult, FailureKind, OperationFailure
from ..diagnostics import Diagnostic, from_model_error
from ..graph._trace_frontier import _TraceFrontier
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..storage.project import ProjectSource
from ..storage.relation_index import build_project_relation_index
from .show import _preflight, _verify_current


class TraceTraversal(_TraceFrontier):
    """Cooperative traversal of an immutable supplied index, without I/O.

    One work unit visits one node or consumes one of its directed edge views.
    The live object retains the frontier and an unfinished adjacency cursor.
    This is process-local continuation, not a serializable Work checkpoint.
    """


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
