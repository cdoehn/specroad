"""Closed JSON request projection of the same parameter contracts used to bind.

Uses the JSON Schema 2020-12 validation vocabulary; no schema fetch or execution.
"""

from .parameters import exclusive_pairs


def _option_schema(option):
    value = option.value_contract.as_schema()
    return {"type": "array", "minItems": 1, "items": value} if option.repeatable else value


def request_schema(command):
    """The closed structured Python request accepted by this exact CommandSpec."""
    options = {"type": "object", "additionalProperties": False,
               "properties": {opt.flag: _option_schema(opt) for opt in command.options},
               "required": [opt.flag for opt in command.options if opt.required]}
    exclusions = [list(pair) for pair in exclusive_pairs(command.options)]
    if exclusions:
        options["allOf"] = [{"not": {"required": pair}} for pair in exclusions]
    arguments = {"type": "object", "additionalProperties": False,
                 "properties": {arg.name: arg.value_contract.as_schema() for arg in command.positionals},
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


