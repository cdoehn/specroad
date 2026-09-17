"""Only completed built-in commands are installed in the runtime registry."""

from .registry import CommandClass, CommandRegistry, CommandSpec, EffectScope, OptionSpec, PreflightProfile
from .results import CommandResult, FailureKind, OperationFailure
from .contracts import CommandProtocol, PositionalSpec, WorkContract
from .result_schemas import validate_result_document


def _published_result(invocation, payload):
    validate_result_document(invocation.command.protocol.result_schema, payload)
    return CommandResult(invocation.command.command_id, result=payload)


def _help(invocation) -> CommandResult:
    return _published_result(invocation, {
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


def _distribution_result(invocation, producer) -> CommandResult:
    from ..runtime.identity import BuildMetadataError
    try:
        payload = producer()
    except BuildMetadataError as error:
        raise OperationFailure(FailureKind.ENVIRONMENT, "Distribution identity is unavailable.") from error
    return _published_result(invocation, payload)


def _version(invocation) -> CommandResult:
    from ..runtime.identity import version_info
    return _distribution_result(invocation, version_info)


def _describe(invocation) -> CommandResult:
    from .self_description import describe_command
    return _published_result(invocation, describe_command(invocation.registry, invocation.arguments["command"]))


def _capabilities(invocation) -> CommandResult:
    from .capabilities import capabilities
    return _distribution_result(invocation, lambda: capabilities(invocation.registry))


def _schema_list(invocation) -> CommandResult:
    from ..model.schema_catalog import SchemaCatalog
    return _published_result(invocation, SchemaCatalog(invocation.registry).list())


def _schema_show(invocation) -> CommandResult:
    from ..model.schema_catalog import SchemaCatalog, SchemaLookupError
    from .command_errors import CommandUsageError
    try:
        payload = SchemaCatalog(invocation.registry).show(invocation.arguments["schema_id"])
    except SchemaLookupError as error:
        raise CommandUsageError("Unknown schema identity") from error
    return _published_result(invocation, payload)


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
    ), CommandSpec(
        command_id="schema.list", words=("schema", "list"),
        command_class=CommandClass.READ_ONLY, preflight_profile=PreflightProfile.BOOTSTRAP,
        effect_scope=EffectScope.NONE, handler=_schema_list,
        options=(OptionSpec("--format", takes_value=True, choices=("pretty", "json")),
                 OptionSpec("--no-color"), OptionSpec("--quiet")),
        protocol=CommandProtocol("schema-catalog-v1", {
            "command_id": "schema.list", "options": {"--format": "json"}},
            work=WorkContract("schema_catalog", ("distribution_schemas",))),
    ), CommandSpec(
        command_id="schema.show", words=("schema", "show"),
        command_class=CommandClass.READ_ONLY, preflight_profile=PreflightProfile.BOOTSTRAP,
        effect_scope=EffectScope.NONE, handler=_schema_show,
        options=(OptionSpec("--format", takes_value=True, choices=("pretty", "json")),
                 OptionSpec("--no-color"), OptionSpec("--quiet")),
        positionals=(PositionalSpec("schema_id"),),
        protocol=CommandProtocol("schema-document-v1", {
            "command_id": "schema.show", "arguments": {"schema_id": "json-envelope-v2"},
            "options": {"--format": "json"}},
            work=WorkContract("schema_lookup", ("distribution_schemas",))),
    )))
