"""One parameter vocabulary feeds the CLI binder and the JSON request schema."""

from dataclasses import dataclass
import re

from .command_errors import CommandUsageError


def _sequence(value, name):
    if not isinstance(value, (tuple, list)):
        raise CommandUsageError(name + " must be an explicit sequence")
    return tuple(value)


@dataclass(frozen=True)
class ValueContract:
    takes_value: bool
    choices: tuple[str, ...]
    option: bool

    def validate(self, value):
        if not self.takes_value:
            if value is not True:
                raise CommandUsageError("Flag must be true or omitted")
            return
        if (not isinstance(value, str) or not value or "\0" in value
                or (self.option and value.startswith("--"))
                or (self.choices and value not in self.choices)):
            raise CommandUsageError("Invalid parameter value")
        try:
            value.encode("utf-8")
        except UnicodeError as error:
            raise CommandUsageError("Parameter value is not valid Unicode") from error

    def as_schema(self):
        if not self.takes_value:
            return {"const": True}
        schema = {"type": "string", "minLength": 1,
                  "pattern": r"^[^\u0000\uD800-\uDFFF]+$"}
        if self.option:
            schema["not"] = {"pattern": "^--"}
        if self.choices:
            schema["enum"] = list(self.choices)
        return schema


def exclusive_pairs(options):
    return tuple(sorted({tuple(sorted((option.flag, other)))
                         for option in options for other in option.excludes}))


@dataclass(frozen=True)
class OptionSpec:
    flag: str
    takes_value: bool = False
    repeatable: bool = False
    choices: tuple[str, ...] = ()
    required: bool = False
    excludes: tuple[str, ...] = ()

    @property
    def value_contract(self):
        return ValueContract(self.takes_value, self.choices, option=True)

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

    @property
    def value_contract(self):
        return ValueContract(True, self.choices, option=False)

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


