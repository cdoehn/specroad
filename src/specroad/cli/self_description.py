"""Executable CLI data contracts projected from the active trusted registry."""

from .contracts import CommandUsageError
from .results import FORMAT_VERSION
from .parameters import exclusive_pairs
from .request_schema import request_schema

DESCRIPTION_VERSION = "1.0.0"


def published_contract(registry, command_id):
    command = registry.resolve_selector(command_id)
    if command.protocol is None:
        raise CommandUsageError("Command has no published machine contract")
    protocol = command.protocol
    # Binding is validation only. Describing a writer must never execute it.
    registry.bind_request(protocol.example)
    return command, protocol


def command_surface(command):
    """Identity, spelling and class shared by all registry projections."""
    return {"command_id": command.command_id,
            "words": list(command.words), "aliases": [list(route) for route in sorted(command.aliases)],
            "command_class": command.command_class.value,
            "preflight_profile": command.preflight_profile.value}


def output_formats(command):
    return next((list(opt.choices) for opt in command.options if opt.flag == "--format"), ["pretty"])


def describe_command(registry, command_id):
    command, protocol = published_contract(registry, command_id)
    formats = output_formats(command)
    return {
        "format_version": DESCRIPTION_VERSION,
        **command_surface(command),
        "budget_policy_version": command.budget_policy_version,
        "lock_kind": protocol.lock_kind,
        "work": protocol.work.as_dict(),
        "parameters": [{"name": arg.name, "kind": "positional", "datatype": "string",
                        "required": arg.required, "choices": list(arg.choices)} for arg in command.positionals],
        "options": [{"flag": opt.flag, "datatype": "string" if opt.takes_value else "boolean",
                     "repeatable": opt.repeatable, "required": opt.required,
                     "choices": list(opt.choices), "excludes": sorted(opt.excludes)}
                    for opt in sorted(command.options, key=lambda item: item.flag)],
        "mutually_exclusive": [list(pair) for pair in exclusive_pairs(command.options)],
        "stdin": {"mode": "unused", "explicit_markers": []},
        "stdout": {"formats": formats, "default_format": "pretty", "json_envelope_version": FORMAT_VERSION,
                   "result_schema": protocol.result_schema,
                   "continuation": {"supported": protocol.work.continuation_supported,
                                    "sarif_fallback": None}},
        "diagnostic_codes": sorted(set(protocol.diagnostic_codes) | {"CORE_USAGE", "CORE_INTERNAL", "CORE_ENVIRONMENT"}),
        "exit_codes": sorted(set(protocol.handler_exit_codes) | {2, 4, 5}),
        "write_effects": {"scope": command.effect_scope.value, "required_write_paths": list(command.requires_write_paths),
                          "external_work": list(protocol.work.external_side_effects)},
        "requires_project": command.requires_project, "requires_git": command.requires_git,
        "request_schema": request_schema(command),
        "examples": [protocol.example.as_dict()],
    }
