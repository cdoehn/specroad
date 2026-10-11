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
        "scope": "Core bootstrap and environment diagnosis; model operations remain separate.",
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


def _schema_result(invocation, schema_id=None) -> CommandResult:
    from ..model.schema_catalog import SchemaCatalog, SchemaLookupError
    from .command_errors import CommandUsageError
    catalog = SchemaCatalog(invocation.registry)
    if schema_id is None:
        return _published_result(invocation, catalog.list())
    try:
        payload = catalog.show(schema_id)
    except SchemaLookupError as error:
        raise CommandUsageError("Unknown schema identity") from error
    return _published_result(invocation, payload)


def _schema_list(invocation) -> CommandResult:
    return _schema_result(invocation)


def _schema_show(invocation) -> CommandResult:
    return _schema_result(invocation, invocation.arguments["schema_id"])


def _environment(invocation) -> CommandResult:
    from ..runtime.environment import environment_report
    from ..diagnostics import Diagnostic
    payload, code = environment_report(invocation)
    validate_result_document(invocation.command.protocol.result_schema, payload)
    diagnostics = ()
    if payload['metadata'] is not None and payload['metadata']['preflight_detail_required']:
        diagnostics = (Diagnostic('SRV167', 'info', 'preflight_detail_required',
                                 'Additional bounded metadata phases were required.'),)
    if code:
        kind = FailureKind(code)
        return CommandResult.failed(invocation.command.command_id, kind, complete=True,
            result=payload, diagnostics=(*diagnostics,
                Diagnostic('CORE_' + kind.name, 'error', kind.name.lower(),
                           'A requested environment prerequisite is blocked.')))
    return CommandResult(invocation.command.command_id, result=payload, diagnostics=diagnostics)


def _initialize(invocation):
    from ..authoring.initialization import initialize_command
    return initialize_command(invocation)


def _inspect(invocation):
    from ..authoring.project_inspection import inspect_command
    return inspect_command(invocation)


def builtin_registry() -> CommandRegistry:
    return CommandRegistry((CommandSpec(
        command_id='init', words=('init',), command_class=CommandClass.ROOT_CREATION,
        preflight_profile=PreflightProfile.ROOT_CREATION, effect_scope=EffectScope.NEW_ROOT,
        handler=_initialize, positionals=(PositionalSpec('path', required=False),),
        requires_write_paths=('path',),
        options=(OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
                 OptionSpec('--no-color'), OptionSpec('--quiet')),
        protocol=CommandProtocol('project-init-v1', {'command_id': 'init',
            'arguments': {'path': 'specroad-project'}, 'options': {'--format': 'json'}},
            handler_exit_codes=(0, 3, 6, 7), diagnostic_codes=('CORE_MODEL', 'CORE_CONFLICT', 'CORE_SECURITY'),
            lock_kind='bootstrap', work=WorkContract('root_creation', ('distribution_resources', 'target_directory'))),
    ), CommandSpec(
        command_id='project.inspect', words=('project', 'inspect'),
        command_class=CommandClass.READ_ONLY, preflight_profile=PreflightProfile.PROJECT_METADATA,
        effect_scope=EffectScope.NONE, handler=_inspect, requires_project=True,
        options=(OptionSpec('--project', takes_value=True),
                 OptionSpec('--profile', takes_value=True, repeatable=True),
                 OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
                 OptionSpec('--no-color'), OptionSpec('--quiet')),
        protocol=CommandProtocol('project-inspect-v1', {'command_id': 'project.inspect',
            'options': {'--format': 'json'}}, handler_exit_codes=(0, 2, 3, 4, 5, 6, 7),
            diagnostic_codes=('CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_CONFLICT', 'CORE_SECURITY',
                              'VALIDATION_UNAVAILABLE'),
            work=WorkContract('project_inspection', ('project_configuration', 'current_model', 'runtime_metadata'))),
    ), CommandSpec(
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
    ), CommandSpec(
        command_id='environment.check', words=('environment', 'check'),
        command_class=CommandClass.READ_ONLY, preflight_profile=PreflightProfile.PROJECT_METADATA,
        effect_scope=EffectScope.NONE, handler=_environment, configuration_schema_required=True,
        budget_policy_version='runtime-budget-v2',
        options=(OptionSpec('--project', takes_value=True), OptionSpec('--for-command', takes_value=True),
                 OptionSpec('--resource-profile', takes_value=True, choices=('constrained', 'standard')),
                 OptionSpec('--cpu-budget-ms', takes_value=True), OptionSpec('--wall-budget-ms', takes_value=True),
                 OptionSpec('--memory-budget-mib', takes_value=True), OptionSpec('--scratch-budget-mib', takes_value=True),
                 OptionSpec('--step-cpu-ms', takes_value=True), OptionSpec('--step-wall-ms', takes_value=True),
                 OptionSpec('--metrics'),
                 OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
                 OptionSpec('--no-color'), OptionSpec('--quiet')),
        protocol=CommandProtocol('environment-v1', {
            'command_id': 'environment.check', 'options': {'--format': 'json'}},
            handler_exit_codes=(0, 2, 3, 5, 6, 7),
            diagnostic_codes=('SRV167', 'CORE_MODEL', 'CORE_SECURITY', 'CORE_CONFLICT'),
            work=WorkContract('environment_metadata', ('runtime_identity', 'distribution_metadata'))),
    )))
