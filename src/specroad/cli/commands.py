"""Only completed built-in commands are installed in the runtime registry."""

from .registry import CommandClass, CommandRegistry, CommandSpec, EffectScope, OptionSpec, PreflightProfile
from .results import CommandResult, FailureKind, OperationFailure
from .contracts import CommandProtocol, PositionalSpec, WorkContract


def _help(invocation) -> CommandResult:
    return CommandResult(invocation.command.command_id, result={
        "usage": "specroad --help [--format pretty|json] [--no-color] [--quiet]",
        "options": [{"flag": "--format", "values": ["pretty", "json"]},
                    {"flag": "--no-color"}, {"flag": "--quiet"}],
        "commands": [{"command_id": cmd.command_id, "words": list(cmd.words),
                      "aliases": [list(alias) for alias in cmd.aliases]}
                     for cmd in invocation.registry.commands],
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


def _describe(invocation) -> CommandResult:
    from .self_description import describe_command
    return CommandResult(invocation.command.command_id,
                         result=describe_command(invocation.registry, invocation.arguments["command"]))


def _capabilities(invocation) -> CommandResult:
    from .capabilities import capabilities
    from ..runtime.identity import BuildMetadataError
    try:
        payload = capabilities(invocation.registry)
    except BuildMetadataError as error:
        raise OperationFailure(FailureKind.ENVIRONMENT, "Distribution identity is unavailable.") from error
    return CommandResult(invocation.command.command_id, result=payload)


def builtin_registry() -> CommandRegistry:
    return CommandRegistry((CommandSpec(
        command_id="help", words=("--help",), aliases=(("-h",),),
        command_class=CommandClass.READ_ONLY,
        preflight_profile=PreflightProfile.BOOTSTRAP,
        effect_scope=EffectScope.NONE, handler=_help,
        protocol=CommandProtocol("help-v1", {"command_id": "help", "options": {"--format": "json"}},
            work=WorkContract("registry_projection", ("command_registry",))),
        options=(OptionSpec("--format", takes_value=True, choices=("pretty", "json")),
                 OptionSpec("--no-color"), OptionSpec("--quiet")),
    ), CommandSpec(
        command_id="version", words=("version",),
        command_class=CommandClass.READ_ONLY,
        preflight_profile=PreflightProfile.BOOTSTRAP,
        effect_scope=EffectScope.NONE, handler=_version,
        protocol=CommandProtocol("version-info-v1", {"command_id": "version", "options": {"--format": "json"}},
            work=WorkContract("distribution_identity", ("distribution_metadata", "runtime_identity"))),
        options=(OptionSpec("--format", takes_value=True, choices=("pretty", "json")),
                 OptionSpec("--no-color"), OptionSpec("--quiet")),
    ), CommandSpec(
        command_id="command.describe", words=("command", "describe"),
        command_class=CommandClass.READ_ONLY, preflight_profile=PreflightProfile.BOOTSTRAP,
        effect_scope=EffectScope.NONE, handler=_describe,
        options=(OptionSpec("--format", takes_value=True, choices=("pretty", "json")),
                 OptionSpec("--no-color"), OptionSpec("--quiet")),
        positionals=(PositionalSpec("command"),),
        protocol=CommandProtocol("command-description-v1", {
            "command_id": "command.describe", "arguments": {"command": "version"}, "options": {"--format": "json"}},
            work=WorkContract("registry_projection", ("command_registry",))),
    ), CommandSpec(
        command_id="capabilities", words=("capabilities",),
        command_class=CommandClass.READ_ONLY, preflight_profile=PreflightProfile.BOOTSTRAP,
        effect_scope=EffectScope.NONE, handler=_capabilities,
        options=(OptionSpec("--format", takes_value=True, choices=("pretty", "json")),
                 OptionSpec("--no-color"), OptionSpec("--quiet")),
        protocol=CommandProtocol("capabilities-v1", {
            "command_id": "capabilities", "options": {"--format": "json"}},
            work=WorkContract("registry_projection", ("command_registry", "distribution_metadata"))),
    )))
