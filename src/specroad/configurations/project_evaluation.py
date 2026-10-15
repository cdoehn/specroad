"""Read-only configuration evaluation over fresh, rechecked project sources."""
from ..cli.result_schemas import validate_result_document
from ..cli.results import CommandResult, FailureKind, OperationFailure
from ..diagnostics import Diagnostic, from_model_error
from ..model.errors import ModelError
from ..query._read_errors import read_details, read_failure
from ..query.read_work import complete_read_command, complete_read_steps
from ..query.show import _preflight, _verify_current
from ..security import SafetyViolation
from ..storage._relation_snapshot import _capture_sources
from ..storage.project import ProjectSource
from .evaluation import ConfigurationEvaluationError, evaluate_configuration


COMMAND = 'configuration.evaluate'


def _evaluate_steps(root, configuration_id):
    project = None
    details = read_details()
    try:
        source = ProjectSource(root)
        project = {'project_root': str(source.boundary.root), 'project_id': source.configuration.project_id}
        _preflight(source)
        snapshot = _capture_sources(source)
        yield 'loaded'
        evaluation = evaluate_configuration(snapshot.records, configuration_id)
        payload = evaluation.data
        details.update(observation_sha256=snapshot.binding.sha256,
                       validation_scope=evaluation.validation_scope, profile_defaults_applied=False)
        yield 'evaluated'
        _preflight(source)
        _verify_current(source, snapshot.binding)
        validate_result_document('configuration-evaluation-v1', payload)
        diagnostics = tuple(Diagnostic('SRV131', 'error', 'model',
            'An applicable artifact requires an excluded artifact.',
            artifact_id=item['source_id'], related_ids=(item['target_id'],),
            rationale='configuration_dependency_excluded') for item in payload['inconsistent_dependencies'])
        if diagnostics:
            return CommandResult.failed(COMMAND, FailureKind.MODEL, complete=True, result=payload,
                                        project=project, diagnostics=diagnostics, details=details)
        return CommandResult(COMMAND, result=payload, project=project, details=details)
    except ConfigurationEvaluationError as error:
        return CommandResult.failed(COMMAND, FailureKind.MODEL, project=project,
            diagnostics=(from_model_error(error, code=error.code),), details=details)
    except (OperationFailure, ModelError, SafetyViolation, OSError) as error:
        return read_failure(COMMAND, error, project, details)


def evaluate_project_configuration(root, configuration_id):
    return complete_read_steps(_evaluate_steps(root, configuration_id))


def configuration_evaluate_command(invocation):
    return complete_read_command(invocation, _evaluate_steps, invocation.arguments['configuration_id'])
