"""Only completed built-in commands are installed in the runtime registry."""

from dataclasses import replace

from ..model._bundle_scope_contract import SCOPE_KINDS as BUNDLE_SCOPE_KINDS
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


def _show(invocation):
    from ..query.show import show_command
    return show_command(invocation)


def _trace(invocation):
    from ..query.trace import trace_command
    return trace_command(invocation)


def _why(invocation):
    from ..query.why import why_command
    return why_command(invocation)


def _roadmap_explain(invocation):
    from ..planning.project_explanation import roadmap_explain_command
    return roadmap_explain_command(invocation)


def _impact(invocation):
    from ..query.impact import impact_command
    return impact_command(invocation)


def _query(invocation):
    from ..query.project_query import query_command
    return query_command(invocation)


def _diff(invocation):
    from ..query.project_diff import diff_command
    return diff_command(invocation)


def _configuration_evaluate(invocation):
    from ..configurations.project_evaluation import configuration_evaluate_command
    return configuration_evaluate_command(invocation)


def _export(invocation):
    from ..exchange.project_export import export_command
    return export_command(invocation)


def _bundle_create(invocation):
    from ..bundles.publication import create_command
    return create_command(invocation)


def _bundle_verify(invocation):
    from ..bundles.verification_command import verify_command
    return verify_command(invocation)


def _bundle_extract(invocation):
    from ..bundles.extraction_command import extract_command
    return extract_command(invocation)


def _read_runtime_options():
    return (OptionSpec('--resource-profile', takes_value=True, choices=('constrained', 'standard')),
            *(OptionSpec(flag, takes_value=True) for flag in ('--cpu-budget-ms', '--wall-budget-ms',
                '--memory-budget-mib', '--scratch-budget-mib', '--step-cpu-ms', '--step-wall-ms')),
            OptionSpec('--metrics'))


def builtin_registry() -> CommandRegistry:
    commands = (CommandSpec(
        command_id='bundle.extract', words=('bundle', 'extract'), command_class=CommandClass.ROOT_CREATION,
        preflight_profile=PreflightProfile.ROOT_CREATION, effect_scope=EffectScope.NEW_ROOT,
        handler=_bundle_extract, positionals=(PositionalSpec('file'),), requires_write_paths=('output',),
        options=(OptionSpec('--output', takes_value=True, required=True),
            OptionSpec('--expected-sha256', takes_value=True),
            OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
            OptionSpec('--no-color'), OptionSpec('--quiet')),
        protocol=CommandProtocol('bundle-extract-v1', {'command_id': 'bundle.extract',
            'arguments': {'file': 'project.zip'}, 'options': {'--output': 'project', '--format': 'json'}},
            handler_exit_codes=(0, 3, 4, 5, 6, 7),
            diagnostic_codes=('CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_CONFLICT', 'CORE_SECURITY',
                              'SRV001', 'SRV002', 'SRV003', 'SRV060', 'SRV083'),
            lock_kind='bootstrap', work=WorkContract('root_creation', ('verified_bundle_input', 'target_directory'))),
    ), CommandSpec(
        command_id='bundle.verify', words=('bundle', 'verify'), command_class=CommandClass.READ_ONLY,
        preflight_profile=PreflightProfile.INPUT_READ, effect_scope=EffectScope.NONE, handler=_bundle_verify,
        positionals=(PositionalSpec('file'),),
        options=(OptionSpec('--expected-sha256', takes_value=True),
            OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
            OptionSpec('--no-color'), OptionSpec('--quiet')),
        protocol=CommandProtocol('bundle-verify-v1', {'command_id': 'bundle.verify',
            'arguments': {'file': 'project.zip'}, 'options': {'--format': 'json'}},
            handler_exit_codes=(0, 3, 4, 5, 6, 7),
            diagnostic_codes=('CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_CONFLICT', 'CORE_SECURITY',
                              'SRV001', 'SRV002', 'SRV003', 'SRV060', 'SRV083'),
            work=WorkContract('native_bundle_verification', ('explicit_bundle_input', 'optional_external_hash'))),
    ), CommandSpec(
        command_id='bundle.create', words=('bundle', 'create'),
        command_class=CommandClass.GENERATED_OUTPUT, preflight_profile=PreflightProfile.PROJECT_READ,
        effect_scope=EffectScope.EXTERNAL_OUTPUT, handler=_bundle_create, requires_project=True,
        configuration_schema_required=True,
        options=(OptionSpec('--scope', takes_value=True, choices=BUNDLE_SCOPE_KINDS),
            *(OptionSpec('--' + name, takes_value=True) for name in
              ('output', 'output-root', 'configuration', 'document', 'release', 'project')),
            OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
            OptionSpec('--no-color'), OptionSpec('--quiet')),
        protocol=CommandProtocol('bundle-create-v1', {'command_id': 'bundle.create',
            'options': {'--scope': 'project', '--output': 'generated/project.zip', '--format': 'json'}},
            handler_exit_codes=(0, 2, 3, 4, 5, 6, 7),
            diagnostic_codes=('CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_CONFLICT', 'CORE_SECURITY',
                              'SRV001', 'SRV002', 'SRV003', 'SRV060', 'SRV083'),
            work=WorkContract('native_project_bundle', ('project_configuration', 'current_project_inventory',
                                                       'empty_completed_receipt_inventory'))),
    ), CommandSpec(
        command_id='export', words=('export',), command_class=CommandClass.GENERATED_OUTPUT,
        preflight_profile=PreflightProfile.PROJECT_READ, effect_scope=EffectScope.EXTERNAL_OUTPUT,
        handler=_export, requires_project=True, configuration_schema_required=True,
        positionals=(PositionalSpec('exchange_format', choices=('reqif', 'reqifz', 'csv', 'ndjson')),),
        options=(OptionSpec('--scope', takes_value=True, choices=('project', 'document', 'query', 'release')),
            OptionSpec('--boundary-policy', takes_value=True, choices=('closed', 'partial')),
            *(OptionSpec('--' + name, takes_value=True) for name in ('output', 'output-root', 'mapping',
                'mapping-sha256', 'csv-profile', 'csv-profile-sha256', 'document', 'release', 'query',
                'configuration', 'xml-limits', 'max-archive-bytes', 'project')),
            OptionSpec('--profile', takes_value=True, repeatable=True),
            OptionSpec('--include-attachments'), OptionSpec('--fail-on-loss'),
            OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
            OptionSpec('--no-color'), OptionSpec('--quiet')),
        protocol=CommandProtocol('exchange-export-v1', {'command_id': 'export',
            'arguments': {'exchange_format': 'ndjson'}, 'options': {'--scope': 'project',
                '--output': 'generated/exchange.ndjson', '--mapping': 'example:export@1.0.0',
                '--mapping-sha256': '3dace6b5a437068945ec537d7d9c4035f17a61ff0400b21f39a3321c8d2ed84c',
                '--format': 'json'}},
            handler_exit_codes=(0, 2, 3, 4, 5, 6, 7),
            diagnostic_codes=('CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_CONFLICT', 'CORE_SECURITY',
                              'SRV001', 'SRV002', 'SRV090', 'SRV130'),
            work=WorkContract('native_scope_export', ('project_configuration', 'current_project_inventory',
                                                     'scope_and_exact_mapping_bindings'))),
    ), CommandSpec(
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
        command_id='artifact.show', words=('artifact', 'show'), aliases=(('show',),),
        command_class=CommandClass.READ_ONLY, preflight_profile=PreflightProfile.PROJECT_READ,
        effect_scope=EffectScope.NONE, handler=_show, requires_project=True,
        positionals=(PositionalSpec('id'),),
        options=(OptionSpec('--project', takes_value=True),
                 OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
                 OptionSpec('--no-color'), OptionSpec('--quiet')),
        protocol=CommandProtocol('artifact-show-v1', {'command_id': 'artifact.show',
            'arguments': {'id': 'SR-GOAL-' + '0' * 26}, 'options': {'--format': 'json'}},
            handler_exit_codes=(0, 2, 3, 4, 5, 6, 7),
            diagnostic_codes=('CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_CONFLICT', 'CORE_SECURITY',
                              'SRV001', 'SRV002'),
            work=WorkContract('artifact_show', ('project_configuration', 'current_project_artifacts',
                                              'complete_relation_references'))),
    ), CommandSpec(
        command_id='trace', words=('trace',), command_class=CommandClass.READ_ONLY,
        preflight_profile=PreflightProfile.PROJECT_READ, effect_scope=EffectScope.NONE,
        handler=_trace, requires_project=True, positionals=(PositionalSpec('id'),),
        options=(OptionSpec('--direction', takes_value=True, required=True, choices=('in', 'out', 'both')),
                 OptionSpec('--depth', takes_value=True, required=True),
                 OptionSpec('--project', takes_value=True),
                 OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
                 OptionSpec('--no-color'), OptionSpec('--quiet')),
        protocol=CommandProtocol('artifact-trace-v1', {'command_id': 'trace',
            'arguments': {'id': 'SR-GOAL-' + '0' * 26},
            'options': {'--direction': 'both', '--depth': '3', '--format': 'json'}},
            handler_exit_codes=(0, 2, 3, 4, 5, 6, 7),
            diagnostic_codes=('CORE_USAGE', 'CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_CONFLICT',
                              'CORE_SECURITY', 'SRV001', 'SRV002'),
            work=WorkContract('artifact_trace', ('project_configuration', 'current_project_artifacts',
                                               'complete_relation_references', 'explicit_trace_scope'))),
    ), CommandSpec(
        command_id='why', words=('why',), command_class=CommandClass.READ_ONLY,
        preflight_profile=PreflightProfile.PROJECT_READ, effect_scope=EffectScope.NONE,
        handler=_why, requires_project=True, positionals=(PositionalSpec('id'),),
        options=(OptionSpec('--project', takes_value=True),
                 OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
                 OptionSpec('--no-color'), OptionSpec('--quiet')),
        protocol=CommandProtocol('artifact-why-v1', {'command_id': 'why',
            'arguments': {'id': 'SR-GOAL-' + '0' * 26}, 'options': {'--format': 'json'}},
            handler_exit_codes=(0, 2, 3, 4, 5, 6, 7),
            diagnostic_codes=('CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_CONFLICT',
                              'CORE_SECURITY', 'SRV001', 'SRV002'),
            work=WorkContract('artifact_why', ('project_configuration', 'current_project_artifacts',
                                             'complete_relation_references', 'configured_trace_depth'))),
    ), CommandSpec(
        command_id='roadmap.explain', words=('roadmap', 'explain'), command_class=CommandClass.READ_ONLY,
        preflight_profile=PreflightProfile.PROJECT_READ, effect_scope=EffectScope.NONE,
        handler=_roadmap_explain, requires_project=True, positionals=(PositionalSpec('id'),),
        options=(OptionSpec('--project', takes_value=True),
                 OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
                 OptionSpec('--no-color'), OptionSpec('--quiet')),
        protocol=CommandProtocol('roadmap-explain-v1', {'command_id': 'roadmap.explain',
            'arguments': {'id': 'SR-GOAL-' + '0' * 26}, 'options': {'--format': 'json'}},
            handler_exit_codes=(0, 2, 3, 4, 5, 6, 7),
            diagnostic_codes=('CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_CONFLICT',
                              'CORE_SECURITY', 'SRV001', 'SRV002'),
            work=WorkContract('roadmap_explanation', ('project_configuration', 'configured_project_inventory',
                'complete_relation_references', 'configured_trace_depth'))),
    ), CommandSpec(
        command_id='impact', words=('impact',), command_class=CommandClass.READ_ONLY,
        preflight_profile=PreflightProfile.PROJECT_READ, effect_scope=EffectScope.NONE,
        handler=_impact, requires_project=True, positionals=(PositionalSpec('id'),),
        options=(OptionSpec('--project', takes_value=True),
                 OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
                 OptionSpec('--no-color'), OptionSpec('--quiet')),
        protocol=CommandProtocol('artifact-impact-v1', {'command_id': 'impact',
            'arguments': {'id': 'SR-GOAL-' + '0' * 26}, 'options': {'--format': 'json'}},
            handler_exit_codes=(0, 1, 2, 3, 4, 5, 6, 7),
            diagnostic_codes=('CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_CONFLICT',
                              'CORE_SECURITY', 'SRV001', 'SRV002', 'SRV025', 'SRV026', 'SRV027'),
            work=WorkContract('artifact_impact', ('project_configuration', 'current_project_artifacts',
                                                'complete_relation_review_history'))),
    ), CommandSpec(
        command_id='query', words=('query',), command_class=CommandClass.READ_ONLY,
        preflight_profile=PreflightProfile.PROJECT_READ, effect_scope=EffectScope.NONE,
        handler=_query, requires_project=True,
        options=(*(OptionSpec('--' + name, takes_value=True, repeatable=True) for name in
            ('type', 'maturity', 'implementation-status', 'verification-plan-status',
             'verification-result', 'owner', 'tag', 'release', 'has-relation', 'missing-relation',
             'full-text', 'filter', 'select', 'sort')),
            *(OptionSpec('--' + name, takes_value=True) for name in ('evaluation', 'offset', 'limit', 'configuration')),
            OptionSpec('--project', takes_value=True),
            OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
            OptionSpec('--no-color'), OptionSpec('--quiet')),
        protocol=CommandProtocol('artifact-query-v1', {'command_id': 'query',
            'options': {'--type': ['goal'], '--limit': '10', '--format': 'json'}},
            handler_exit_codes=(0, 2, 3, 4, 5, 6, 7),
            diagnostic_codes=('CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_CONFLICT', 'CORE_SECURITY',
                              'SRV001', 'SRV002', 'SRV110', 'SRV130'),
            work=WorkContract('artifact_query', ('project_configuration', 'current_project_artifacts',
                                               'explicit_query_and_srx_inputs'))),
    ), CommandSpec(
        command_id='configuration.evaluate', words=('configuration', 'evaluate'),
        command_class=CommandClass.READ_ONLY, preflight_profile=PreflightProfile.PROJECT_READ,
        effect_scope=EffectScope.NONE, handler=_configuration_evaluate, requires_project=True,
        positionals=(PositionalSpec('configuration_id'),),
        options=(OptionSpec('--project', takes_value=True),
            OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
            OptionSpec('--no-color'), OptionSpec('--quiet')),
        protocol=CommandProtocol('configuration-evaluation-v1', {'command_id': 'configuration.evaluate',
            'arguments': {'configuration_id': 'SR-CFG-' + '0' * 26}, 'options': {'--format': 'json'}},
            handler_exit_codes=(0, 2, 3, 4, 5, 6, 7),
            diagnostic_codes=('CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_CONFLICT', 'CORE_SECURITY',
                              'SRV001', 'SRV002', 'SRV130', 'SRV131'),
            work=WorkContract('configuration_evaluation', ('project_configuration', 'current_project_artifacts',
                'selected_configuration_chain', 'stored_strong_relations'))),
    ), CommandSpec(
        command_id='diff', words=('diff',), command_class=CommandClass.READ_ONLY,
        preflight_profile=PreflightProfile.PROJECT_READ, effect_scope=EffectScope.NONE,
        handler=_diff, requires_project=True,
        options=(OptionSpec('--against', takes_value=True, required=True),
            OptionSpec('--against-kind', takes_value=True, choices=('git', 'local')),
            OptionSpec('--configuration', takes_value=True),
            OptionSpec('--project', takes_value=True),
            OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
            OptionSpec('--no-color'), OptionSpec('--quiet')),
        protocol=CommandProtocol('artifact-diff-v1', {'command_id': 'diff',
            'options': {'--against': '.', '--against-kind': 'local', '--format': 'json'}},
            handler_exit_codes=(0, 2, 3, 4, 5, 6, 7),
            diagnostic_codes=('CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_CONFLICT', 'CORE_SECURITY',
                              'SRV001', 'SRV002', 'SRV130', 'SRV131'),
            work=WorkContract('artifact_diff', ('current_comparison_source', 'same_project_comparison_base'))),
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
    ))
    from .document_commands import read_commands
    from .metadata_commands import metadata_commands
    commands += read_commands()
    commands += metadata_commands()
    readers = {'artifact.show', 'query', 'trace', 'why', 'impact', 'diff', 'configuration.evaluate', 'roadmap.explain', 'export', 'bundle.verify', 'render', 'view.render', 'diagram'}
    return CommandRegistry(tuple(replace(command, options=command.options + _read_runtime_options(),
        budget_policy_version='runtime-budget-v2') if command.command_id in readers else command
        for command in commands))
