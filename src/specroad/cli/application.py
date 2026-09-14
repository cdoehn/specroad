"""Renderer-free dispatcher shared by every supported entry point."""

from dataclasses import replace

from .commands import builtin_registry
from .options import OptionResolutionError, resolve_options
from .registry import CommandExecutionError, CommandRegistry, CommandUsageError


def dispatch(arguments: list[str] | tuple[str, ...], *, registry: CommandRegistry | None = None,
             cwd=None, profile_layers=(), configuration_layer=None) -> int:
    try:
        selected = builtin_registry() if registry is None else registry
        invocation = selected.parse(arguments)
        invocation = replace(invocation, resolved=resolve_options(
            invocation, cwd=cwd, profile_layers=profile_layers,
            configuration_layer=configuration_layer))
        return selected.execute(invocation)
    except OptionResolutionError as error:
        return error.exit_code
    except CommandUsageError:
        return 2
    except CommandExecutionError:
        return 4
