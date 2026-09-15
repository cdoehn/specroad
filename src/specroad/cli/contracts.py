"""Declarative trusted-Core commands. This is metadata, not a plugin loader.

A command class describes its allowed effects; it does not sandbox arbitrary
Python. Only built-in handlers may be registered by production code.
"""

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Callable, Mapping
import re
import inspect

if TYPE_CHECKING:
    from .option_values import ResolvedOptions


class CommandUsageError(ValueError):
    """Invalid command declaration or invocation; nothing has been executed."""


class CommandExecutionError(RuntimeError):
    """A registered handler did not obey its execution contract."""


def _sequence(value, name):
    if not isinstance(value, (tuple, list)):
        raise CommandUsageError(name + " must be an explicit sequence")
    return tuple(value)


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
            values = _sequence(getattr(self, name), name)
            if not all(isinstance(value, str) and value for value in values):
                raise CommandUsageError("Option values must be nonempty strings")
            if len(values) != len(set(values)):
                raise CommandUsageError("Duplicate option constraint")
            object.__setattr__(self, name, values)
        if self.choices and not self.takes_value:
            raise CommandUsageError("A flag cannot have value choices")


@dataclass(frozen=True)
class PositionalSpec:
    name: str
    required: bool = True
    choices: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.name, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", self.name):
            raise CommandUsageError("Invalid positional argument name")
        if type(self.required) is not bool:
            raise CommandUsageError("Argument requirement must be a boolean")
        values = _sequence(self.choices, "choices")
        if not all(isinstance(value, str) and value and "\0" not in value for value in values):
            raise CommandUsageError("Invalid argument choice")
        if len(values) != len(set(values)):
            raise CommandUsageError("Duplicate argument choice")
        try:
            for value in values:
                value.encode("utf-8")
        except UnicodeError as error:
            raise CommandUsageError("Invalid argument choice Unicode") from error
        object.__setattr__(self, "choices", values)


@dataclass(frozen=True)
class WorkContract:
    """Explicit non-resumable minimum step of the currently available handlers.

    Declaring metadata cannot install a work engine. Its later implementation
    must extend this contract together with the actual execution capability.
    """
    minimum_step: str = "handler_call"
    required_inputs: tuple[str, ...] = ()
    continuation_supported: bool = False
    external_side_effects: tuple[str, ...] = ()
    checkpoint_algorithms: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.minimum_step, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", self.minimum_step):
            raise CommandUsageError("Invalid minimum-step identity")
        for name in ("required_inputs", "external_side_effects", "checkpoint_algorithms"):
            values = _sequence(getattr(self, name), name)
            if (any(not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_.-]*", value) for value in values)
                    or len(values) != len(set(values))):
                raise CommandUsageError("Invalid work contract sequence")
            object.__setattr__(self, name, values)
        if self.continuation_supported is not False or self.external_side_effects or self.checkpoint_algorithms:
            raise CommandUsageError("The current Core has no published work-resume engine")

    def as_dict(self):
        return {"continuation_supported": False, "external_side_effects": [],
                "checkpoint_algorithms": [],
                "minimum_step": {"kind": self.minimum_step, "required_inputs": list(self.required_inputs),
                    "limits": {"memory_bytes": None, "cpu_seconds": None}, "limits_status": "unmeasured",
                    "on_blocked": "fail_without_checkpoint", "blocked_exit_code": 5}}


@dataclass(frozen=True)
class CommandProtocol:
    """Trusted machine contract; examples are inert requests, never callbacks."""
    result_schema: str
    example: object
    handler_exit_codes: tuple[int, ...] = (0,)
    diagnostic_codes: tuple[str, ...] = ()
    lock_kind: str = "none"
    work: WorkContract = field(default_factory=WorkContract)

    def __post_init__(self):
        from .requests import CommandRequest
        if self.lock_kind != "none" or not isinstance(self.work, WorkContract):
            raise CommandUsageError("Unsupported lock or work protocol")
        if not isinstance(self.result_schema, str) or not re.fullmatch(r"[a-z][a-z0-9._-]*", self.result_schema):
            raise CommandUsageError("Invalid result schema identity")
        example = self.example if isinstance(self.example, CommandRequest) else CommandRequest.from_mapping(self.example)
        object.__setattr__(self, "example", example)
        codes = _sequence(self.handler_exit_codes, "handler_exit_codes")
        if (not codes or any(type(code) is not int or code not in range(8) for code in codes)
                or len(codes) != len(set(codes))):
            raise CommandUsageError("Invalid completed handler exit codes")
        object.__setattr__(self, "handler_exit_codes", codes)
        diagnostics = _sequence(self.diagnostic_codes, "diagnostic_codes")
        if (any(not isinstance(code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", code) for code in diagnostics)
                or len(diagnostics) != len(set(diagnostics))):
            raise CommandUsageError("Invalid diagnostic code declaration")
        object.__setattr__(self, "diagnostic_codes", diagnostics)


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
    positionals: tuple[PositionalSpec, ...] = ()
    protocol: CommandProtocol | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.command_id, str) or not re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*", self.command_id):
            raise CommandUsageError("Invalid canonical command ID")
        for name, cls in (("command_class", CommandClass), ("preflight_profile", PreflightProfile), ("effect_scope", EffectScope)):
            try:
                object.__setattr__(self, name, cls(getattr(self, name)))
            except (ValueError, TypeError) as error:
                raise CommandUsageError("Unknown command contract category") from error
        if (not callable(self.handler) or inspect.iscoroutinefunction(self.handler)
                or inspect.isgeneratorfunction(self.handler)
                or inspect.iscoroutinefunction(getattr(self.handler, "__call__", None))
                or inspect.isgeneratorfunction(getattr(self.handler, "__call__", None))):
            raise CommandUsageError("An executable built-in handler is required")
        object.__setattr__(self, "words", _sequence(self.words, "words"))
        object.__setattr__(self, "aliases", tuple(_sequence(alias, "alias") for alias in _sequence(self.aliases, "aliases")))
        object.__setattr__(self, "options", _sequence(self.options, "options"))
        object.__setattr__(self, "requires_write_paths", _sequence(self.requires_write_paths, "requires_write_paths"))
        for words in (self.words, *self.aliases):
            if not words or not all(isinstance(word, str) and re.fullmatch(r"(?:[a-z][a-z0-9-]*|--help|-h)", word) for word in words):
                raise CommandUsageError("Invalid command spelling")
        if any(type(value) is not bool for value in (self.requires_project, self.requires_git)):
            raise CommandUsageError("Requirements must be booleans")
        if not all(isinstance(option, OptionSpec) for option in self.options):
            raise CommandUsageError("Invalid option contract")
        positions = _sequence(self.positionals, "positionals")
        if not all(isinstance(arg, PositionalSpec) for arg in positions):
            raise CommandUsageError("Invalid positional contract")
        if len({arg.name for arg in positions}) != len(positions):
            raise CommandUsageError("Duplicate positional argument")
        optional_seen = False
        for arg in positions:
            if optional_seen and arg.required:
                raise CommandUsageError("Required arguments must precede optional arguments")
            optional_seen = optional_seen or not arg.required
        object.__setattr__(self, "positionals", positions)
        if self.protocol is not None and (not isinstance(self.protocol, CommandProtocol)
                or self.protocol.example.command_id != self.command_id):
            raise CommandUsageError("Protocol example must address its own command")
        flags = [option.flag for option in self.options]
        if len(flags) != len(set(flags)):
            raise CommandUsageError("Duplicate option flag")
        for option in self.options:
            if any(other not in flags or other == option.flag for other in option.excludes):
                raise CommandUsageError("Exclusion refers to an unknown option or itself")
        normative_flags = {"--actor-type", "--actor-id", "--request-id", "--dry-run", "--as-proposal"}
        if self.command_class is not CommandClass.NORMATIVE_WRITE and normative_flags.intersection(flags):
            raise CommandUsageError("Normative write option on a non-write command")
        if not all(isinstance(path, str) and re.fullmatch(r"[a-z][a-z0-9_]*", path) for path in self.requires_write_paths):
            raise CommandUsageError("Write prerequisites name declared arguments, not paths")
        if len(self.requires_write_paths) != len(set(self.requires_write_paths)):
            raise CommandUsageError("Duplicate write prerequisite")
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
    resolved: "ResolvedOptions | None" = None
    arguments: Mapping[str, str] = field(default_factory=dict)
    registry: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "options", MappingProxyType(dict(self.options)))
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))


