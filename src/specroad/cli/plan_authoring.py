"""Registered native Markdown write commands; JSON input remains passive."""
from .contracts import CommandProtocol, PositionalSpec, WorkContract
from .registry import CommandClass, CommandSpec, EffectScope, OptionSpec, PreflightProfile
from .results import CommandResult, OperationFailure, FailureKind
from ..model.plan_command_ids import COMMANDS


def plan_command(invocation):
    from ..authoring.inputs import _read_input
    from ..authoring.native_plan import author_plan
    from ..storage.json_syntax import parse_json_object
    from ..model.errors import ModelError
    from ..security import SafetyViolation
    from ..bundles.errors import BundleError
    options = invocation.options
    try:
        command = invocation.command.command_id
        intent = {'command_id': command}
        if 'target' in invocation.arguments:
            intent['target'] = invocation.arguments['target']
        for flag, key in (('--plan', 'plan_id'), ('--parent', 'parent_id'), ('--target-plan', 'target_plan_id')):
            if flag in options:
                intent[key] = options[flag]
        if '--position' in options:
            text = options['--position']
            if not text.isascii() or not text.isdigit():
                raise OperationFailure(FailureKind.USAGE, 'Nonnegative position required')
            intent['position'] = int(text)
        if '--subtree' in options:
            intent['subtree'] = options['--subtree']
        if '--input' in options:
            intent['fields'] = parse_json_object(_read_input(options['--input'], invocation.resolved.working_directory, None))
        proposal = None
        if '--proposal-input' in options:
            proposal = parse_json_object(_read_input(options['--proposal-input'], invocation.resolved.working_directory, None))
        outcome = author_plan(invocation.resolved.project_root, intent,
            actor={'actor_type': options['--actor-type'], 'actor_id': options['--actor-id']},
            request_id=options.get('--request-id'), dry_run=options.get('--dry-run', False),
            expected_model_root=options.get('--expected-model-root-sha256'),
            as_proposal=options.get('--as-proposal', False), proposal_fields=proposal,
            force=options.get('--force', False), force_reason=options.get('--force-reason'),
            authority=invocation.publication_authority, services=invocation.restore_services)
        from .results import ResultStatus
        force_fields = (dict(force=outcome['force'], validation_status=outcome['validation_status'],
            status=ResultStatus(outcome['status'])) if 'force' in outcome else {})
        return CommandResult(command, **force_fields, result={'format_version': 'plan-authoring-command-v1',
            'command_id': command, 'outcome': outcome})
    except (ModelError, BundleError, SafetyViolation, OSError) as error:
        if isinstance(error, SafetyViolation):
            code = 7
        elif isinstance(error, OSError):
            code = 5
        else:
            code = getattr(error, 'exit_code', 3)
        raise OperationFailure(FailureKind(code), getattr(error, 'reason', 'Plan authoring failed'),
            details={'authoring_attempt': getattr(error, 'authoring_attempt', None), 'diagnostic': error.diagnostic() if isinstance(error, ModelError) else {},
                     'impact': getattr(error, 'impact', [])}) from error


def plan_commands():
    result = []
    for command in COMMANDS:
        args = () if command == 'plan.create' else (PositionalSpec('target'),)
        fields = command in ('plan.create', 'plan.update', 'plan.entry.add', 'plan.entry.update')
        options = [OptionSpec('--actor-type', takes_value=True, required=True, choices=('human', 'ai', 'ci', 'tool')),
            OptionSpec('--actor-id', takes_value=True, required=True),
            OptionSpec('--request-id', takes_value=True), OptionSpec('--dry-run'),
            OptionSpec('--as-proposal'), OptionSpec('--proposal-input', takes_value=True),
            OptionSpec('--expected-model-root-sha256', takes_value=True),
            OptionSpec('--project', takes_value=True),
            OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
            OptionSpec('--no-color'), OptionSpec('--quiet')]
        example = {'--actor-type': 'human', '--actor-id': 'author'}
        if fields:
            options.append(OptionSpec('--input', takes_value=True, required=True))
            example['--input'] = 'fields.json'
        if command.startswith('plan.entry.'):
            options.append(OptionSpec('--plan', takes_value=True))
        if command in ('plan.entry.add', 'plan.entry.move'):
            options.extend((OptionSpec('--parent', takes_value=True, required=command.endswith('.move')),
                            OptionSpec('--position', takes_value=True, required=command.endswith('.move'))))
            if command.endswith('.move'):
                options.append(OptionSpec('--target-plan', takes_value=True, required=True))
                example.update({'--parent': 'SR-IPLAN-' + '0'*26,
                                '--target-plan': 'SR-IPLAN-' + '0'*26, '--position': '0'})
        if command in ('plan.remove', 'plan.entry.remove'):
            options.append(OptionSpec('--subtree'))
        request = {'command_id': command, 'options': example}
        if args:
            request['arguments'] = {'target': ('SR-IPLAN-' if command in
                ('plan.update', 'plan.remove', 'plan.entry.add') else 'SR-PENTRY-') + '0'*26}
        result.append(CommandSpec(command, tuple(command.split('.')), CommandClass.NORMATIVE_WRITE,
            PreflightProfile.PROJECT_WRITE, EffectScope.NORMATIVE_TRANSACTION,
            handler=plan_command, requires_project=True, configuration_schema_required=True,
            positionals=args, options=tuple(options), protocol=CommandProtocol('plan-authoring-command-v1',
            request, handler_exit_codes=tuple(range(8)), diagnostic_codes=(
                'CORE_USAGE', 'CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_CONFLICT', 'CORE_SECURITY'),
            lock_kind='writer', work=WorkContract('native_plan_authoring',
                ('complete_current_and_historical_inventory', 'native_target_gates', 'host_authority')))))
    return tuple(result)
