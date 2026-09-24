"""Adapt existing observations to CLI data, without registering a new command."""
from ..result_contract import ResultContractError

def validation_command_result(command, observation):
    """Existing versioned envelope adapter, not a registered CLI command."""
    from ..cli.results import CommandResult, FailureKind
    from .diagnostics import ValidationAssessment
    if type(observation) is not ValidationAssessment:
        raise ResultContractError("Expected a validation assessment")
    kwargs = {"complete": observation.assessment.complete, "diagnostics": observation.diagnostics,
              "result": observation.as_dict(), "details": observation.summary}
    if observation.passed:
        return CommandResult(command, **kwargs)
    return CommandResult.failed(command, FailureKind(observation.exit_code), **kwargs)
