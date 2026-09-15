"""Immutable command registry, binding and execution from one contract source."""

from types import MappingProxyType

from ._arguments import bind_options, bind_values
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
        try:
            for item in arguments:
                item.encode('utf-8')
        except UnicodeError as error:
            raise CommandUsageError("Argument vector is not valid Unicode") from error
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

    def bind_request(self, request) -> Invocation:
        from .requests import CommandRequest
        if not isinstance(request, CommandRequest):
            raise CommandUsageError("A structured CommandRequest is required")
        command = self.resolve(request.command_id)
        return Invocation(command, bind_values(request.options, command.options))

    def invoke(self, arguments: list[str] | tuple[str, ...], **context_inputs) -> int:
        from .application import dispatch
        return dispatch(arguments, registry=self, **context_inputs)

    def execute(self, invocation: Invocation, **context_inputs) -> int:
        return self.execute_result(invocation, **context_inputs).exit_code

    def execute_result(self, invocation: Invocation, **context_inputs) -> CommandResult:
        """Public invocation API: resolve current inputs, never trust old context."""
        from .application import execute_request
        from .requests import CommandRequest
        self._require_registered(invocation)
        request = CommandRequest(invocation.command.command_id, invocation.options)
        return execute_request(request, registry=self, **context_inputs).result

    def _require_registered(self, invocation):
        if (not isinstance(invocation, Invocation)
                or self.resolve(invocation.command.command_id) is not invocation.command):
            raise CommandUsageError("Invocation is not bound to this registry")

    def _run_handler(self, invocation: Invocation) -> CommandResult:
        """Internal prepared-context seam; no alias-specific handler path."""
        self._require_registered(invocation)
        try:
            value = invocation.command.handler(invocation)
            result = normalize_result(value, invocation.command.command_id)
            result.verify_delivery()
            return result
        except (CommandUsageError, OperationFailure, OSError):
            raise
        except Exception as error:
            raise CommandExecutionError("Command handler failed") from error
