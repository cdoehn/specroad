"""All shortest directed paths to origins in a fresh complete project observation."""
from ..cli.result_schemas import validate_result_document
from ..bundles.errors import BundleError
from ..srx.errors import SrxError
from ..cli.results import CommandResult, FailureKind, OperationFailure
from ..diagnostics import Diagnostic, from_model_error
from ..model.errors import ModelError
from .read_work import complete_read_command, complete_read_steps
from ._read_execution import complete_work
from ..security import SafetyViolation
from ..storage.project import ProjectSource
from ..storage.relation_index import build_project_relation_index
from .show import _preflight, _verify_current
from .why_work import WhyTraversal


def _why_paths(index, artifact_id, depth):
    result = complete_work(WhyTraversal(index, artifact_id, depth=depth))
    return result['targets'], result['paths']


def _why_steps(root, artifact_id):
    """Return every shortest path per reachable Goal, Need and Source.

    Stored directions and symmetric inverse views define connectivity. The
    configured trace_depth is semantic scope; absence is not a guessed default.
    The checkpointable producer is driven synchronously by this command.
    """
    project = None
    details = dict(atomic_snapshot=False, full_semantic_validation=False,
                   approval_granted=False, write_authorized=False, recovery_performed=False)
    try:
        from ..bundles._partial_read import partial_read_snapshot
        partial = partial_read_snapshot(root)
        if partial is not None:
            from ._partial_commands import why_steps
            return (yield from why_steps(partial, artifact_id, details=details))
        source = ProjectSource(root)
        project = {'project_root': str(source.boundary.root), 'project_id': source.configuration.project_id}
        _preflight(source)
        limits = source.configuration.data.get('resource_limits', {})
        if 'trace_depth' not in limits:
            raise ModelError('why_depth_not_configured', path='specroad.json',
                             pointer='/resource_limits/trace_depth')
        depth = limits['trace_depth']
        observed = build_project_relation_index(source)
        yield 'loaded'
        targets, paths = _why_paths(observed.adjacency, artifact_id, depth)
        payload = {'format_version': '1.0.0', 'start': artifact_id, 'depth': depth,
                   'traversal': 'stored_direction_with_symmetric_inverses',
                   'targets': targets, 'paths': paths, 'path_count': len(paths),
                   'coverage': {'scope': 'current_project_artifacts',
                       'source_count': observed.source_count, 'relation_count': observed.relation_count,
                       'observation_sha256': observed.binding.sha256,
                       'validation_scope': 'relation_references_canonical_storage_and_hierarchies_only',
                       'atomic_snapshot': False}}
        yield 'evaluated'
        _preflight(source)
        _verify_current(source, observed.binding)
        validate_result_document('artifact-why-v1', payload)
        return CommandResult('why', result=payload, project=project, details=details)
    except (BundleError, SrxError) as error:
        from ._read_errors import read_failure
        return read_failure('why', error, project, details)
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


def why_artifact(root, artifact_id):
    """Complete the same read phases synchronously, without a durable checkpoint."""
    return complete_read_steps(_why_steps(root, artifact_id))


def why_command(invocation):
    return complete_read_command(invocation, _why_steps, invocation.arguments['id'])
