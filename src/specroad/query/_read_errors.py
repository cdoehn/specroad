"""Failure projection for the new live Query and Diff adapters."""
from ..cli.results import CommandResult, FailureKind, OperationFailure
from ..diagnostics import Diagnostic, from_model_error
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..srx.errors import SrxError


def read_failure(command, error, project, details):
    if isinstance(error, OperationFailure):
        code = int(error.kind)
        diagnostic = Diagnostic('CORE_' + error.kind.name, 'error', 'preflight', str(error))
        details = {**error.details, **details}
    elif isinstance(error, ModelError):
        changed = {'configuration_changed', 'relation_source_changed',
                   'relation_index_membership_changed', 'relation_index_source_changed',
                   'comparison_source_changed', 'comparison_source_membership_changed',
                   'show_source_changed', 'show_source_disappeared',
                   'query_input_changed', 'diff_source_changed'}
        code = 6 if error.reason in changed else getattr(error, 'exit_code', 3)
        if error.reason == 'query_sort_value_not_scalar':
            code = 2
        from ..configurations.evaluation import ConfigurationEvaluationError
        diagnostic = from_model_error(error, code='SRV130' if isinstance(error, ConfigurationEvaluationError) else None)
    elif isinstance(error, SrxError):
        code = 3
        diagnostic = Diagnostic(error.code, 'error', 'model', 'SRX input was rejected.',
            rule_id=error.rule_id, location={'pointer': error.pointer}, rationale=error.reason)
        details = {**details, 'srx_failure': error.diagnostic()}
    else:
        code = 7 if isinstance(error, SafetyViolation) else 5
        diagnostic = Diagnostic('CORE_SECURITY' if code == 7 else 'CORE_ENVIRONMENT',
            'error', 'runtime', 'The read command could not safely read its inputs.')
    return CommandResult.failed(command, FailureKind(code), project=project,
                                diagnostics=(diagnostic,), details=details)


def read_details():
    return dict(atomic_snapshot=False, full_semantic_validation=False,
                approval_granted=False, write_authorized=False, recovery_performed=False)
