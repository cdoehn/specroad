"""Structured Python command requests, never executable project configuration.

This is the embedding boundary for the current registry, not the future
Authoring --input file/stdin protocol or an agent/proposal approval mechanism.
Keys in options are the same full flags declared by each CommandSpec.
"""

from dataclasses import dataclass, field
import re
from types import MappingProxyType
from typing import Mapping

from .contracts import CommandUsageError


def _value(value):
    if value is True:
        return value
    if isinstance(value, str) and value and '\0' not in value:
        try:
            value.encode('utf-8')
        except UnicodeError as error:
            raise CommandUsageError("Structured option text must be valid Unicode") from error
        return value
    raise CommandUsageError("Structured option values must be strings or true flags")


@dataclass(frozen=True)
class CommandRequest:
    command_id: str
    options: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.command_id, str) or not re.fullmatch(
                r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*", self.command_id):
            raise CommandUsageError("A canonical command ID is required")
        if not isinstance(self.options, Mapping):
            raise CommandUsageError("Structured options must be a mapping")
        copied = {}
        for flag, value in self.options.items():
            if not isinstance(flag, str) or not re.fullmatch(r"--[a-z][a-z0-9-]*", flag):
                raise CommandUsageError("Structured options require complete option flags")
            if isinstance(value, (tuple, list)):
                if not value:
                    raise CommandUsageError("A repeated option needs at least one value")
                copied[flag] = tuple(_value(item) for item in value)
            else:
                copied[flag] = _value(value)
        object.__setattr__(self, 'options', MappingProxyType(copied))

    @classmethod
    def from_mapping(cls, value):
        """Accept only request data, never handlers or previously resolved state."""
        if (not isinstance(value, Mapping) or 'command_id' not in value
                or set(value) - {'command_id', 'options'}):
            raise CommandUsageError("Invalid structured request fields")
        return cls(value['command_id'], value.get('options', {}))
