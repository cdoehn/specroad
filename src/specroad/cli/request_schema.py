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
    if command.command_id == 'recover.restore':
        from ._restore_metadata import _PLAN, _EXECUTE, _PLAN_REQUIRED, _EXECUTE_REQUIRED
        def mode(required, forbidden):
            return {'required': sorted(required),
                    'not': {'anyOf': [{'required': [name]} for name in sorted(forbidden)]}}
        options.setdefault('allOf', []).append({'anyOf': [
            {'allOf': [mode(_PLAN_REQUIRED, _EXECUTE), {'anyOf': [
                {'properties': {'--source-kind': {'const': 'baseline'}},
                 'required': ['--default-locale', '--generated-path']},
                {'properties': {'--source-kind': {'const': 'project_bundle'}},
                 'not': {'anyOf': [{'required': ['--default-locale']},
                                  {'required': ['--generated-path']}]}}]}]},
            {'allOf': [mode(_EXECUTE_REQUIRED, _PLAN), {'anyOf': [
                {'required': ['--selection-root', '--affected-journals']},
                {'not': {'anyOf': [{'required': ['--selection-root']},
                                  {'required': ['--affected-journals']}]}}]}]}]})
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
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "urn:specroad:schema:1.0.0:request:" + command.command_id,
            "x-specroad-validation-scope": "request_fields_only", "type": "object",
            "additionalProperties": False, "required": required,
            "properties": {"command_id": {"const": command.command_id},
                           "options": options, "arguments": arguments}}
    schema["description"] = "Structured request for " + command.command_id + "; binding never executes example requests."
    if command.protocol is not None:
        schema["examples"] = [command.protocol.example.as_dict()]
    # These describe the existing bootstrap option policy, not inserted values.
    for flag, default in (("--format", "pretty"),):
        field = options["properties"].get(flag)
        if field is not None and (flag != "--format" or "pretty" in field.get("enum", ())):
            field["default"] = default
    return schema
