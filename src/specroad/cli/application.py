"""Renderer-free dispatcher shared by every supported entry point."""

from .commands import builtin_registry
from .registry import CommandExecutionError, CommandRegistry, CommandUsageError


def dispatch(arguments: list[str] | tuple[str, ...], *, registry: CommandRegistry | None = None) -> int:
    try:
        return (builtin_registry() if registry is None else registry).invoke(arguments)
    except CommandUsageError:
        return 2
    except CommandExecutionError:
        return 4
