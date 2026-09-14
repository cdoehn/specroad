"""Renderer-free application boundary shared by all entry points."""

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Mapping

from .commands import builtin_registry
from .options import OptionResolutionError, resolve_options
from .registry import CommandExecutionError, CommandRegistry, CommandUsageError
from .results import CommandResult, FailureKind, failed_result


@dataclass(frozen=True)
class CommandResponse:
    result: CommandResult
    options: Mapping

    def __post_init__(self):
        object.__setattr__(self, "options", MappingProxyType(dict(self.options)))


def _error_options(arguments):
    """Honor an unambiguous error-report format without accepting invalid usage."""
    if not isinstance(arguments, (list, tuple)) or not all(isinstance(item, str) for item in arguments):
        return {}
    formats = []
    for index, item in enumerate(arguments):
        if item.startswith("--format="):
            formats.append(item.partition("=")[2])
        elif item == "--format":
            formats.append(arguments[index + 1] if index + 1 < len(arguments) else None)
    return {"--format": formats[0]} if len(formats) == 1 and formats[0] in ("json", "sarif") else {}


def execute(arguments: list[str] | tuple[str, ...], *, registry: CommandRegistry | None = None,
            cwd=None, profile_layers=(), configuration_layer=None) -> CommandResponse:
    command = "unknown"
    options = _error_options(arguments)
    project = None
    try:
        selected = builtin_registry() if registry is None else registry
        invocation = selected.parse(arguments)
        command = invocation.command.command_id
        options = invocation.options
        invocation = replace(invocation, resolved=resolve_options(
            invocation, cwd=cwd, profile_layers=profile_layers,
            configuration_layer=configuration_layer))
        if invocation.resolved.project_root is not None:
            # Identity and hashes remain unknown until a future model loader binds them.
            project = {"project_root": str(invocation.resolved.project_root),
                       "project_id": None, "model_root_sha256": None}
        outcome = selected.execute_result(invocation)
        if outcome.project is None and project is not None:
            outcome = replace(outcome, project=project)
    except OptionResolutionError as error:
        outcome = failed_result(command, FailureKind(error.exit_code), str(error))
    except CommandUsageError as error:
        outcome = failed_result(command, FailureKind.USAGE, str(error))
    except OSError:
        outcome = failed_result(command, FailureKind.ENVIRONMENT, "A required I/O operation failed.")
    except Exception:
        outcome = failed_result(command, FailureKind.INTERNAL, "An internal command contract failed.")
    return CommandResponse(outcome, options)


def dispatch_result(arguments, **kwargs) -> CommandResult:
    return execute(arguments, **kwargs).result


def dispatch(arguments, **kwargs) -> int:
    return dispatch_result(arguments, **kwargs).exit_code
