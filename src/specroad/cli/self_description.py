"""Executable CLI data contracts projected from the active trusted registry."""

from .contracts import CommandUsageError
from .results import FORMAT_VERSION

DESCRIPTION_VERSION = "1.0.0"


def _text_schema(*, option=False, choices=()):
    schema = {"type": "string", "minLength": 1,
              "pattern": r"^[^\u0000\uD800-\uDFFF]+$"}
    if option:
        schema["not"] = {"pattern": "^--"}
    if choices:
        schema["enum"] = list(choices)
    return schema


def _option_schema(option):
    value = _text_schema(option=True, choices=option.choices) if option.takes_value else {"const": True}
    return {"type": "array", "minItems": 1, "items": value} if option.repeatable else value


def _exclusions(command):
    return [list(pair) for pair in sorted({tuple(sorted((opt.flag, other)))
            for opt in command.options for other in opt.excludes})]


def request_schema(command):
    """The closed structured Python request accepted by this exact CommandSpec."""
    options = {"type": "object", "additionalProperties": False,
               "properties": {opt.flag: _option_schema(opt) for opt in command.options},
               "required": [opt.flag for opt in command.options if opt.required]}
    exclusions = _exclusions(command)
    if exclusions:
        options["allOf"] = [{"not": {"required": pair}} for pair in exclusions]
    arguments = {"type": "object", "additionalProperties": False,
                 "properties": {arg.name: _text_schema(choices=arg.choices) for arg in command.positionals},
                 "required": [arg.name for arg in command.positionals if arg.required]}
    if len(command.positionals) > 1:
        arguments["dependentRequired"] = {arg.name: [prev.name for prev in command.positionals[:index]]
             for index, arg in enumerate(command.positionals) if index}
    required = ["command_id"]
    if options["required"]:
        required.append("options")
    if arguments["required"]:
        required.append("arguments")
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
            "additionalProperties": False, "required": required,
            "properties": {"command_id": {"const": command.command_id},
                           "options": options, "arguments": arguments}}


def describe_command(registry, command_id):
    command = registry.resolve(command_id)
    if command.protocol is None:
        raise CommandUsageError("Command has no published machine contract")
    protocol = command.protocol
    # Binding is validation only. Describing a writer must never execute it.
    registry.bind_request(protocol.example)
    formats = next((list(opt.choices) for opt in command.options if opt.flag == "--format"), ["pretty"])
    return {
        "format_version": DESCRIPTION_VERSION,
        "command_id": command.command_id,
        "words": list(command.words), "aliases": [list(route) for route in sorted(command.aliases)],
        "command_class": command.command_class.value,
        "preflight_profile": command.preflight_profile.value,
        "budget_policy_version": command.budget_policy_version,
        "parameters": [{"name": arg.name, "kind": "positional", "datatype": "string",
                        "required": arg.required, "choices": list(arg.choices)} for arg in command.positionals],
        "options": [{"flag": opt.flag, "datatype": "string" if opt.takes_value else "boolean",
                     "repeatable": opt.repeatable, "required": opt.required,
                     "choices": list(opt.choices), "excludes": sorted(opt.excludes)}
                    for opt in sorted(command.options, key=lambda item: item.flag)],
        "mutually_exclusive": _exclusions(command),
        "stdin": {"mode": "unused", "explicit_markers": []},
        "stdout": {"formats": formats, "default_format": "pretty", "json_envelope_version": FORMAT_VERSION,
                   "result_schema": protocol.result_schema},
        "diagnostic_codes": sorted(set(protocol.diagnostic_codes) | {"CORE_USAGE", "CORE_INTERNAL", "CORE_ENVIRONMENT"}),
        "exit_codes": sorted(set(protocol.handler_exit_codes) | {2, 4, 5}),
        "write_effects": {"scope": command.effect_scope.value, "required_write_paths": list(command.requires_write_paths)},
        "requires_project": command.requires_project, "requires_git": command.requires_git,
        "request_schema": request_schema(command),
        "examples": [protocol.example.as_dict()],
    }
