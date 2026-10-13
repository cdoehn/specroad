"""Renderer-free application boundary shared by all entry points."""

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Mapping

from .commands import builtin_registry
from .options import OptionResolutionError
from .invocation_context import InvocationContextBuilder
from .registry import CommandRegistry, CommandUsageError
from .requests import CommandRequest
from .results import CommandResult, FailureKind, OperationFailure, failed_result
from ..diagnostics import Diagnostic


@dataclass(frozen=True)
class CommandResponse:
    result: CommandResult
    options: Mapping

    def __post_init__(self):
        object.__setattr__(self, "options", MappingProxyType(dict(self.options)))


def _error_options(arguments):
    """Honor an unambiguous error-report format without accepting invalid usage."""
    if isinstance(arguments, CommandRequest):
        arguments = [flag + '=' + value if isinstance(value, str) else flag
                     for flag, value in arguments.options.items()
                     if flag in ("--format", "--quiet", "--no-color")
                     and (isinstance(value, str) or value is True)]
    if not isinstance(arguments, (list, tuple)) or not all(isinstance(item, str) for item in arguments):
        return {}
    formats = []
    for index, item in enumerate(arguments):
        if item.startswith("--format="):
            formats.append(item.partition("=")[2])
        elif item == "--format":
            formats.append(arguments[index + 1] if index + 1 < len(arguments) else None)
    options = {"--format": formats[0]} if len(formats) == 1 and formats[0] in ("json", "sarif") else {}
    for flag in ("--quiet", "--no-color"):
        if arguments.count(flag) == 1:
            options[flag] = True
    return options


def execute(arguments: list[str] | tuple[str, ...] | CommandRequest, *, registry: CommandRegistry | None = None,
            cwd=None, profile_layers=(), configuration_layer=None,
            context_builder: InvocationContextBuilder | None = None, consumption=None) -> CommandResponse:
    if isinstance(arguments, (list, tuple)):
        arguments = tuple(arguments)
    command = "unknown"
    options = _error_options(arguments)
    project = None
    preflight = None
    consumption_call = None
    try:
        selected = builtin_registry() if registry is None else registry
        invocation = (selected.bind_request(arguments) if isinstance(arguments, CommandRequest)
                      else selected.parse(arguments))
        command = invocation.command.command_id
        options = invocation.options
        if (options.get('--metrics') is True or
                invocation.command.budget_policy_version == 'runtime-budget-v2'):
            from ..runtime.budget_policy import RESOURCE_OPTIONS, ResourcePolicyError
            from ..runtime.consumption import WorkConsumption, ConsumptionError
            try:
                targets = {k: v for k, v in options.items() if k in RESOURCE_OPTIONS}
                if targets or options.get('--metrics') is True:
                    work = WorkConsumption() if consumption is None else consumption
                    if type(work) is not WorkConsumption:
                        raise ConsumptionError('An owned work consumption ledger is required')
                    consumption_call = work.begin(targets)
            except (ResourcePolicyError, ConsumptionError) as error:
                raise CommandUsageError(str(error)) from error
        builder = InvocationContextBuilder() if context_builder is None else context_builder
        invocation = builder.prepare(
            invocation, cwd=cwd, profile_layers=profile_layers,
            configuration_layer=configuration_layer)
        invocation = replace(invocation, consumption_call=consumption_call)
        preflight = invocation.resolved.preflight
        if invocation.resolved.project_root is not None:
            # Identity and hashes remain unknown until a future model loader binds them.
            project = {"project_root": str(invocation.resolved.project_root),
                       "project_id": None, "model_root_sha256": None}
        outcome = selected._run_handler(invocation)
    except OperationFailure as error:
        outcome = failed_result(command, error.kind, str(error), complete=error.complete, details=error.details)
    except OptionResolutionError as error:
        outcome = failed_result(command, FailureKind(error.exit_code), str(error), details=error.details)
    except CommandUsageError as error:
        outcome = failed_result(command, FailureKind.USAGE, str(error))
    except OSError:
        outcome = failed_result(command, FailureKind.ENVIRONMENT, "A required I/O operation failed.")
    except Exception:
        outcome = failed_result(command, FailureKind.INTERNAL, "An internal command contract failed.")
    if outcome.project is None and project is not None:
        outcome = replace(outcome, project=project)
    if preflight is not None:
        outcome = replace(outcome, details={**outcome.details, 'preflight': preflight})
    observation = outcome.details.get('preflight')
    if (isinstance(observation, Mapping) and observation.get('preflight_detail_required')
            and not any(d.code == 'SRV167' for d in outcome.diagnostics)):
        outcome = replace(outcome, diagnostics=(*outcome.diagnostics,
            Diagnostic('SRV167', 'info', 'preflight_detail_required',
                       'Additional bounded metadata phases were required.')))
    if consumption_call is not None:
        if options.get('--metrics') is True:
            from ._runtime_metrics import attach_runtime_summary
            outcome = attach_runtime_summary(outcome, command, consumption_call)
        else:
            consumption_call.finish()
    return CommandResponse(outcome, options)


def execute_request(request: CommandRequest | Mapping, **context_inputs) -> CommandResponse:
    """Execute a canonical structured request through the normal CLI pipeline."""
    try:
        current = request if isinstance(request, CommandRequest) else CommandRequest.from_mapping(request)
    except CommandUsageError as error:
        return CommandResponse(failed_result("unknown", FailureKind.USAGE, str(error)), {})
    return execute(current, **context_inputs)


def dispatch_result(arguments, **kwargs) -> CommandResult:
    return execute(arguments, **kwargs).result


def dispatch(arguments, **kwargs) -> int:
    try:
        return dispatch_result(arguments, **kwargs).exit_code
    except OperationFailure as error:
        return int(error.kind)
    except OSError:
        return 5
    except Exception:
        return 4
