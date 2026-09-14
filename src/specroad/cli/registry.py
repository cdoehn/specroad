"""Immutable command registry, binding and execution from one contract source."""

from types import MappingProxyType

from ._arguments import bind_options
from .options import check_global_contract
from .results import CommandResult, OperationFailure, normalize_result
from .contracts import (
    CommandClass, CommandExecutionError, CommandSpec, CommandUsageError,
    EffectScope, Invocation, OptionSpec, PreflightProfile,
)


class CommandRegistry:
    """An immutable validated set, with no unavailable command placeholders."""

    def __init__(self, commands: tuple[CommandSpec, ...]):
        by_id = {}
        routes = {}
        for command in commands:
            if not isinstance(command, CommandSpec) or command.command_id in by_id:
                raise CommandUsageError("Duplicate or invalid command declaration")
            check_global_contract(command)
            by_id[command.command_id] = command
            for route in (command.words, *command.aliases):
                if route in routes:
                    raise CommandUsageError("Duplicate command spelling")
                routes[route] = command
        self._commands = MappingProxyType(by_id)
        self._routes = MappingProxyType(routes)

    @property
    def commands(self) -> tuple[CommandSpec, ...]:
        return tuple(self._commands.values())

    def resolve(self, command_id: str) -> CommandSpec:
        try:
            return self._commands[command_id]
        except (KeyError, TypeError) as error:
            raise CommandUsageError("Command is not implemented") from error

    def parse(self, arguments: list[str] | tuple[str, ...]) -> Invocation:
        if not isinstance(arguments, (list, tuple)) or not arguments or not all(isinstance(arg, str) and arg and "\0" not in arg for arg in arguments):
            raise CommandUsageError("Invalid argument vector")
        candidates = []
        for route, command in self._routes.items():
            try:
                values = bind_options(tuple(arguments), route, command.options)
            except CommandUsageError:
                continue
            candidates.append(Invocation(command, values))
        if len(candidates) != 1:
            raise CommandUsageError("Unknown, invalid or ambiguous invocation")
        return candidates[0]

    def invoke(self, arguments: list[str] | tuple[str, ...]) -> int:
        return self.execute(self.parse(arguments))

    def execute(self, invocation: Invocation) -> int:
        return self.execute_result(invocation).exit_code

    def execute_result(self, invocation: Invocation) -> CommandResult:
        """Execute once and normalize the typed result before any rendering."""
        try:
            value = invocation.command.handler(invocation)
            result = normalize_result(value, invocation.command.command_id)
            result.verify_delivery()
            return result
        except (CommandUsageError, OperationFailure, OSError):
            raise
        except Exception as error:
            raise CommandExecutionError("Command handler failed") from error
