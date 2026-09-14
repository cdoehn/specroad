"""Only completed built-in commands are installed in the runtime registry."""

from .registry import CommandClass, CommandRegistry, CommandSpec, EffectScope, OptionSpec, PreflightProfile
from .results import CommandResult


def _help(invocation) -> CommandResult:
    return CommandResult(invocation.command.command_id, result={
        "usage": "specroad --help [--format pretty|json]",
        "options": [{"flag": "--format", "values": ["pretty", "json"]}],
        "commands": [{"command_id": "help", "words": ["--help"], "aliases": [["-h"]]}],
        "exit_codes": {"0": "completed", "2": "invalid usage", "4": "internal error", "5": "I/O failure"},
        "examples": ["specroad --help", "python3 -m specroad --help --format json"],
        "scope": "Core bootstrap; project commands are not implemented yet.",
    })


def builtin_registry() -> CommandRegistry:
    return CommandRegistry((CommandSpec(
        command_id="help", words=("--help",), aliases=(("-h",),),
        command_class=CommandClass.READ_ONLY,
        preflight_profile=PreflightProfile.BOOTSTRAP,
        effect_scope=EffectScope.NONE, handler=_help,
        options=(OptionSpec("--format", takes_value=True, choices=("pretty", "json")),),
    ),))
