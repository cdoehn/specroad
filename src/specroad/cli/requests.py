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
    arguments: Mapping[str, object] = field(default_factory=dict)

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
        if not isinstance(self.arguments, Mapping):
            raise CommandUsageError("Structured arguments must be a mapping")
        arguments = {}
        for name, value in self.arguments.items():
            if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", name):
                raise CommandUsageError("Invalid structured argument")
            if isinstance(value, (list, tuple)):
                if not value or not all(isinstance(item, str) for item in value):
                    raise CommandUsageError("Invalid repeated argument")
                arguments[name] = tuple(_value(item) for item in value)
            elif isinstance(value, str):
                arguments[name] = _value(value)
            else:
                raise CommandUsageError("Invalid scalar argument")
        object.__setattr__(self, 'arguments', MappingProxyType(arguments))

    def as_dict(self):
        return {"command_id": self.command_id,
                "options": {key: list(value) if isinstance(value, tuple) else value
                            for key, value in self.options.items()},
                "arguments": {key:list(value) if isinstance(value,tuple) else value for key,value in self.arguments.items()}}

    @classmethod
    def from_mapping(cls, value):
        """Accept only request data, never handlers or previously resolved state."""
        if (not isinstance(value, Mapping) or 'command_id' not in value
                or set(value) - {'command_id', 'options', 'arguments', 'force', 'force_reason'}):
            raise CommandUsageError("Invalid structured request fields")
        options = value.get('options', {})
        if not isinstance(options, Mapping):
            raise CommandUsageError('Structured options must be a mapping')
        options = dict(options)
        if 'force' in value or 'force_reason' in value:
            from ..force import ForceRequest, ForceContractError
            try:
                request = ForceRequest(value.get('force', False), value.get('force_reason'))
            except (ForceContractError, UnicodeError) as error:
                raise CommandUsageError('Invalid explicit Force request') from error
            if '--force' in options or '--force-reason' in options:
                raise CommandUsageError('Force must have exactly one explicit spelling')
            if request.requested:
                options['--force'] = True
            if request.reason is not None:
                options['--force-reason'] = request.reason
        return cls(value['command_id'], options, value.get('arguments', {}))
