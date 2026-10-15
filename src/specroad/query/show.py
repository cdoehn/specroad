"""Complete artifact and relation views; no cache writes or approval claims."""
from hashlib import sha256

from ..cli.result_schemas import validate_result_document
from ..cli.results import CommandResult, FailureKind, OperationFailure
from ..diagnostics import Diagnostic, from_model_error
from ..model.errors import ModelError
from .read_work import complete_read_command, complete_read_steps
from ..model.paths import PathClass
from ..runtime.preflight import require_project_read_preflight
from ..security import SafetyViolation
from ..storage.preflight_metadata import MetadataPhases
from ..storage.project import ProjectSource
from ..storage.relation_index import read_project_relation_views
from ..storage.resource_discovery import current_json_paths
from ._show_projection import show_payload


def _preflight(source):
    require_project_read_preflight(source.boundary, source.configuration_bytes, MetadataPhases())


def _verify_current(source, binding):
    try:
        _verify_bound_sources(source, binding)
    except FileNotFoundError as error:
        raise ModelError('show_source_disappeared') from error


def _verify_bound_sources(source, binding):
    # The public reader binds all artifact bytes, including unrelated and
    # relation-free sources. Recheck that observation after the final preflight.
    def paths():
        return tuple(p for p in current_json_paths(source) if source.classify(p) is PathClass.ARTIFACT)

    source.check_current()
    if (str(source.boundary.root) != binding.source_root
            or source.boundary._root_identity != binding.root_identity
            or source.configuration.project_id != binding.project_id
            or sha256(source.configuration_bytes).hexdigest() != binding.configuration_sha256
            or paths() != tuple(p for p, _ in binding.resources)):
        raise ModelError('show_source_changed')
    for path, digest in binding.resources:
        if sha256(source.read_normative(path)).hexdigest() != digest:
            raise ModelError('show_source_changed', path=path)
    if paths() != tuple(p for p, _ in binding.resources):
        raise ModelError('show_source_changed')
    source.check_current()


def _show_steps(root, artifact_id, *, index=None, strategy='indexed'):
    """Read the current complete source set even with a prior/partial index hint.

    The result checks common artifact fields, references and canonical relation
    storage. It does not grant full semantic validation, approval or an atomic
    snapshot against noncooperating writers. Optional persistent caches stay off.
    """
    project = None
    details = dict(atomic_snapshot=False, full_semantic_validation=False,
                   approval_granted=False, write_authorized=False, recovery_performed=False)
    try:
        source = ProjectSource(root)
        project = {'project_root': str(source.boundary.root),
                   'project_id': source.configuration.project_id}
        _preflight(source)
        observed = read_project_relation_views(source, artifact_id, index=index, strategy=strategy)
        yield 'loaded'
        payload = show_payload(observed)
        yield 'evaluated'
        _preflight(source)
        _verify_current(source, observed.binding)
        validate_result_document('artifact-show-v1', payload)
        return CommandResult('artifact.show', result=payload, project=project, details=details)
    except OperationFailure as error:
        return CommandResult.failed('artifact.show', error.kind, project=project,
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
                'error', 'runtime', 'Artifact query could not safely read its inputs.')
        return CommandResult.failed('artifact.show', FailureKind(code), project=project,
                                    diagnostics=(diagnostic,), details=details)


def show_artifact(root, artifact_id, *, index=None, strategy='indexed'):
    """Complete the same read phases synchronously, without a durable checkpoint."""
    return complete_read_steps(_show_steps(root, artifact_id, index=index, strategy=strategy))


def show_command(invocation):
    return complete_read_command(invocation, _show_steps, invocation.arguments['id'])
