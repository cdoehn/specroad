"""Only completed built-in commands are installed in the runtime registry."""

from .registry import CommandClass, CommandRegistry, CommandSpec, EffectScope, OptionSpec, PreflightProfile
from .results import CommandResult, FailureKind, OperationFailure


def _help(invocation) -> CommandResult:
    return CommandResult(invocation.command.command_id, result={
        "usage": "specroad --help [--format pretty|json] [--no-color] [--quiet]",
        "options": [{"flag": "--format", "values": ["pretty", "json"]},
                    {"flag": "--no-color"}, {"flag": "--quiet"}],
        "commands": [{"command_id": "help", "words": ["--help"], "aliases": [["-h"]]},
                     {"command_id": "version", "words": ["version"], "aliases": []}],
        "exit_codes": {"0": "completed", "2": "invalid usage", "4": "internal error", "5": "I/O failure"},
        "examples": ["specroad --help", "specroad version --format json"],
        "scope": "Core bootstrap; project commands are not implemented yet.",
    })


def _version(invocation) -> CommandResult:
    from ..runtime.identity import BuildMetadataError, version_info
    try:
        payload = version_info()
    except BuildMetadataError as error:
        raise OperationFailure(FailureKind.ENVIRONMENT, "Distribution identity is unavailable.") from error
    return CommandResult(invocation.command.command_id, result=payload)


def builtin_registry() -> CommandRegistry:
    return CommandRegistry((CommandSpec(
        command_id="help", words=("--help",), aliases=(("-h",),),
        command_class=CommandClass.READ_ONLY,
        preflight_profile=PreflightProfile.BOOTSTRAP,
        effect_scope=EffectScope.NONE, handler=_help,
        options=(OptionSpec("--format", takes_value=True, choices=("pretty", "json")),
                 OptionSpec("--no-color"), OptionSpec("--quiet")),
    ), CommandSpec(
        command_id="version", words=("version",),
        command_class=CommandClass.READ_ONLY,
        preflight_profile=PreflightProfile.BOOTSTRAP,
        effect_scope=EffectScope.NONE, handler=_version,
        options=(OptionSpec("--format", takes_value=True, choices=("pretty", "json")),
                 OptionSpec("--no-color"), OptionSpec("--quiet")),
    )))
