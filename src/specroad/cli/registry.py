"""Declarative trusted-Core commands. This is metadata, not a plugin loader.

A command class describes its allowed effects; it does not sandbox arbitrary
Python. Only built-in handlers may be registered by production code.
"""

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Callable, Mapping
import re


class CommandUsageError(ValueError):
    """Invalid command declaration or invocation; nothing has been executed."""


class CommandClass(str, Enum):
    NORMATIVE_WRITE = "normative_write"
    PLAN_OUTPUT = "plan_output"
    GENERATED_OUTPUT = "generated_output"
    READ_ONLY = "read_only"
    LOCAL_OPERATIONAL = "local_operational"
    RECOVERY_WRITE = "recovery_write"
    ROOT_CREATION = "root_creation"
    WORK_OPERATIONAL = "work_operational"


class PreflightProfile(str, Enum):
    BOOTSTRAP = "bootstrap"
    INPUT_READ = "input_read"
    PROJECT_METADATA = "project_metadata"
    PROJECT_READ = "project_read"
    PROJECT_WRITE = "project_write"
    ROOT_CREATION = "root_creation"
    RECOVERY = "recovery"


class EffectScope(str, Enum):
    NONE = "none"
    EXTERNAL_OUTPUT = "external_output"
    NORMATIVE_TRANSACTION = "normative_transaction"
    LOCAL_OPERATIONAL = "local_operational"
    RECOVERY_TRANSACTION = "recovery_transaction"
    NEW_ROOT = "new_root"
    EXTERNAL_WORK = "external_work"


@dataclass(frozen=True)
class OptionSpec:
    flag: str
    takes_value: bool = False
    repeatable: bool = False
    choices: tuple[str, ...] = ()
    required: bool = False
    excludes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.flag, str) or not re.fullmatch(r"--[a-z][a-z0-9-]*", self.flag):
            raise CommandUsageError("Invalid option flag")
        if any(type(value) is not bool for value in (self.takes_value, self.repeatable, self.required)):
            raise CommandUsageError("Option switches must be booleans")
        for name in ("choices", "excludes"):
            values = tuple(getattr(self, name))
            if not all(isinstance(value, str) and value for value in values):
                raise CommandUsageError("Option values must be nonempty strings")
            if len(values) != len(set(values)):
                raise CommandUsageError("Duplicate option constraint")
            object.__setattr__(self, name, values)
        if self.choices and not self.takes_value:
            raise CommandUsageError("A flag cannot have value choices")


@dataclass(frozen=True)
class CommandSpec:
    command_id: str
    words: tuple[str, ...]
    command_class: CommandClass
    preflight_profile: PreflightProfile
    effect_scope: EffectScope
    handler: Callable
    options: tuple[OptionSpec, ...] = ()
    aliases: tuple[tuple[str, ...], ...] = ()
    requires_project: bool = False
    requires_git: bool = False
    requires_write_paths: tuple[str, ...] = ()
    # No resource-budget implementation or supported version is claimed yet.
    budget_policy_version: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.command_id, str) or not re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*", self.command_id):
            raise CommandUsageError("Invalid canonical command ID")
        for name, cls in (("command_class", CommandClass), ("preflight_profile", PreflightProfile), ("effect_scope", EffectScope)):
            try:
                object.__setattr__(self, name, cls(getattr(self, name)))
            except (ValueError, TypeError) as error:
                raise CommandUsageError("Unknown command contract category") from error
        if not callable(self.handler):
            raise CommandUsageError("An executable built-in handler is required")
        object.__setattr__(self, "words", tuple(self.words))
        object.__setattr__(self, "aliases", tuple(tuple(alias) for alias in self.aliases))
        object.__setattr__(self, "options", tuple(self.options))
        object.__setattr__(self, "requires_write_paths", tuple(self.requires_write_paths))
        for words in (self.words, *self.aliases):
            if not words or not all(isinstance(word, str) and re.fullmatch(r"(?:[a-z][a-z0-9-]*|--help|-h)", word) for word in words):
                raise CommandUsageError("Invalid command spelling")
        if any(type(value) is not bool for value in (self.requires_project, self.requires_git)):
            raise CommandUsageError("Requirements must be booleans")
        if not all(isinstance(option, OptionSpec) for option in self.options):
            raise CommandUsageError("Invalid option contract")
        flags = [option.flag for option in self.options]
        if len(flags) != len(set(flags)):
            raise CommandUsageError("Duplicate option flag")
        if not all(isinstance(path, str) and re.fullmatch(r"[a-z][a-z0-9_]*", path) for path in self.requires_write_paths):
            raise CommandUsageError("Write prerequisites name declared arguments, not paths")
        allowed_scopes = {
            CommandClass.READ_ONLY: {EffectScope.NONE, EffectScope.EXTERNAL_OUTPUT},
            CommandClass.PLAN_OUTPUT: {EffectScope.EXTERNAL_OUTPUT},
            CommandClass.GENERATED_OUTPUT: {EffectScope.EXTERNAL_OUTPUT},
            CommandClass.NORMATIVE_WRITE: {EffectScope.NORMATIVE_TRANSACTION},
            CommandClass.LOCAL_OPERATIONAL: {EffectScope.LOCAL_OPERATIONAL},
            CommandClass.RECOVERY_WRITE: {EffectScope.RECOVERY_TRANSACTION},
            CommandClass.ROOT_CREATION: {EffectScope.NEW_ROOT},
            CommandClass.WORK_OPERATIONAL: {EffectScope.EXTERNAL_WORK},
        }
        if self.effect_scope not in allowed_scopes[self.command_class]:
            raise CommandUsageError("Side-effect boundary contradicts command class")
        if self.preflight_profile is PreflightProfile.BOOTSTRAP and (self.requires_project or self.requires_git or self.requires_write_paths or self.effect_scope is not EffectScope.NONE):
            raise CommandUsageError("Bootstrap must not require project, Git or writes")
        if self.budget_policy_version is not None and (not isinstance(self.budget_policy_version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", self.budget_policy_version)):
            raise CommandUsageError("Invalid budget policy version")


@dataclass(frozen=True)
class Invocation:
    command: CommandSpec
    options: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "options", MappingProxyType(dict(self.options)))


class CommandRegistry:
    """An immutable validated set, with no unavailable command placeholders."""

    def __init__(self, commands: tuple[CommandSpec, ...]):
        by_id = {}
        routes = {}
        for command in commands:
            if not isinstance(command, CommandSpec) or command.command_id in by_id:
                raise CommandUsageError("Duplicate or invalid command declaration")
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
        argv = tuple(arguments)
        matches = [(route, command) for route, command in self._routes.items() if argv[:len(route)] == route]
        if not matches:
            raise CommandUsageError("Unknown command")
        route, command = max(matches, key=lambda item: len(item[0]))
        option_specs = {option.flag: option for option in command.options}
        values = {}
        index = len(route)
        while index < len(argv):
            token = argv[index]
            flag, equals, attached = token.partition("=")
            option = option_specs.get(flag)
            if option is None or (flag in values and not option.repeatable):
                raise CommandUsageError("Unknown or repeated option")
            if option.takes_value:
                if equals:
                    value = attached
                else:
                    index += 1
                    if index >= len(argv):
                        raise CommandUsageError("Missing option value")
                    value = argv[index]
                if not value or value.startswith("--") or (option.choices and value not in option.choices):
                    raise CommandUsageError("Invalid option value")
            else:
                if equals:
                    raise CommandUsageError("Flag does not accept a value")
                value = True
            values[flag] = (*values.get(flag, ()), value) if option.repeatable else value
            index += 1
        for option in command.options:
            if option.required and option.flag not in values:
                raise CommandUsageError("Missing required option")
            if option.flag in values and any(other in values for other in option.excludes):
                raise CommandUsageError("Mutually exclusive options")
        return Invocation(command, values)

    def invoke(self, arguments: list[str] | tuple[str, ...]) -> int:
        invocation = self.parse(arguments)
        return invocation.command.handler(invocation)
