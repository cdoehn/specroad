"""Raw public adapters for native creation, updates, relations and lifecycle."""
from ..diagnostics.catalog import known_codes
from .contracts import CommandProtocol, PositionalSpec, WorkContract
from .registry import CommandClass, CommandSpec, EffectScope, OptionSpec, PreflightProfile
from .results import CommandResult, OperationFailure, FailureKind
from ..model.authoring_command_ids import COMMANDS, BASIC_COMMANDS, SPECIAL_COMMANDS, CREATE_KINDS, CREATE_FIELDS


def common_options():
    return (OptionSpec('--actor-type', takes_value=True, required=True, choices=('human', 'ai', 'ci', 'tool')),
        OptionSpec('--actor-id', takes_value=True, required=True), OptionSpec('--request-id', takes_value=True),
        OptionSpec('--dry-run'), OptionSpec('--as-proposal'), OptionSpec('--proposal-input', takes_value=True),
        OptionSpec('--expected-model-root-sha256', takes_value=True), OptionSpec('--project', takes_value=True),
        OptionSpec('--format', takes_value=True, choices=('pretty', 'json')), OptionSpec('--quiet'), OptionSpec('--no-color'))


def _integer(value):
    if not value.isascii() or not value.isdigit():
        raise OperationFailure(FailureKind.USAGE, 'Nonnegative integer required')
    return int(value)


def command(invocation):
    from ..authoring.inputs import _read_input, read_artifact_create_input
    from ..authoring.native_generic import author_generic
    from ..changes.json_patch import JsonPatch
    from ..storage.json_syntax import parse_json_object
    from ..model.errors import ModelError
    from ..security import SafetyViolation
    from ..bundles.errors import BundleError
    options = invocation.options; name = invocation.command.command_id
    cwd = invocation.resolved.working_directory
    try:
        intent = {'command_id': name, **invocation.arguments}
        if name == 'change.apply':
            intent['plan_bytes'] = _read_input(invocation.arguments['plan_file'], cwd, None)
            from ..authoring.native_saved import apply_saved
            author_generic = apply_saved
        elif name in SPECIAL_COMMANDS:
            fields = parse_json_object(_read_input(options['--input'], cwd, None)) if '--input' in options else {}
            if 'command_id' in fields:
                raise OperationFailure(FailureKind.USAGE, 'Command is supplied by the registered route')
            # Positional/flag aliases must repeat identical values, never override input.
            def bind(key, value):
                if key in fields and fields[key] != value:
                    raise OperationFailure(FailureKind.USAGE, 'Conflicting explicit authoring inputs')
                fields[key] = value
            if name == 'evidence.record' and 'verification_id' in invocation.arguments and 'record' not in fields:
                fields = {'record': fields}
            for key, value in invocation.arguments.items():
                bind(key, value)
            for flag, key in (('--decision','decision'),('--reason','reason'),('--comment','comment'),
                ('--relation-id','relation_id'),('--configuration','configuration_id'),('--release','release_id'),
                ('--expected-sha256','expected_sha256')):
                if flag in options:
                    bind(key, options[flag])
            if '--expected-revision' in options:
                bind('expected_revision', _integer(options['--expected-revision']))
            if '--run-context' in options:
                run = parse_json_object(_read_input(options['--run-context'], cwd, None))
                if name == 'evidence.import':
                    bind('run_context',run)
                else:
                    record = fields.get('record')
                    if type(record) is not dict or 'run_context' in record and record['run_context'] != run:
                        raise OperationFailure(FailureKind.USAGE, 'Conflicting explicit run context')
                    fields['record'] = {**record, 'run_context': run}
            intent = {'command_id': name, **fields}
        elif name == 'artifact.create':
            fields = {k:v for k,v in options.items() if k not in {o.flag for o in common_options()} | {'--input', '--force', '--force-reason'}}
            prepared = read_artifact_create_input(intent['artifact_type'], options=fields,
                input=options.get('--input'), cwd=cwd)
            intent['fields'] = prepared.fields
        elif name == 'artifact.update':
            if '--input' in options:
                intent['patch'] = JsonPatch.from_bytes(_read_input(options['--input'], cwd, None)).data
            else:
                if invocation.option_order:
                    intent['options'] = [list(p) for p in invocation.option_order if p[0] in ('--set', '--unset')]
                else:
                    if '--set' in options and '--unset' in options:
                        raise OperationFailure(FailureKind.USAGE, 'Ordered input required for mixed field operations')
                    intent['options'] = [[flag, value] for flag in ('--set', '--unset') for value in options.get(flag, ())]
        for flag, key in (('--type','type'), ('--target','target'), ('--relation-id','relation_id'),
                          ('--to','to'), ('--reason','reason'), ('--rationale','rationale'),
                          ('--expected-sha256','expected_sha256')):
            if flag in options and name not in SPECIAL_COMMANDS:
                intent[key] = options[flag]
        for flag, key in (('--expected-revision','expected_revision'), ('--position','position')):
            if flag in options and name not in SPECIAL_COMMANDS:
                intent[key] = _integer(options[flag])
        proposal = parse_json_object(_read_input(options['--proposal-input'], cwd, None)) if '--proposal-input' in options else None
        redirect = dict(force=options.get('--force', False), force_reason=options.get('--force-reason')) if name == 'change.apply' else dict(as_proposal=options.get('--as-proposal',False), proposal_fields=proposal,
            force=options.get('--force', False), force_reason=options.get('--force-reason'))
        result = author_generic(invocation.resolved.project_root, intent,
            actor={'actor_type': options['--actor-type'], 'actor_id': options['--actor-id']},
            request_id=options.get('--request-id'), dry_run=options.get('--dry-run',False),
            expected_model_root=options.get('--expected-model-root-sha256'),
            **redirect,
            authority=invocation.publication_authority, services=invocation.restore_services)
        if result.get('format_version') == 'force-authoring-execution-v1':
            from .results import ResultStatus
            from ..diagnostics import Diagnostic
            diagnostics = tuple(Diagnostic(d.get('code') or 'CORE_MODEL', d.get('severity', 'error'),
                d.get('reason') or 'force_target_diagnostic', d.get('reason') or 'Target validation finding',
                path=d.get('path')) for d in result['diagnostics'])
            return CommandResult(name, status=ResultStatus(result['status']),
                result={'format_version':'native-authoring-command-v1', 'command_id': name, 'outcome': result},
                diagnostics=diagnostics, force=result['force'], validation_status=result['validation_status'])
        return CommandResult(name, result={'format_version':'native-authoring-command-v1',
                                           'command_id':name, 'outcome':result})
    except (ModelError, BundleError, SafetyViolation, OSError) as error:
        code = 7 if isinstance(error, SafetyViolation) else 5 if isinstance(error, OSError) else getattr(error,'exit_code',3)
        raise OperationFailure(FailureKind(code), getattr(error,'reason','Authoring failed'),
            details={'authoring_attempt': getattr(error, 'authoring_attempt', None), 'diagnostic': error.diagnostic() if isinstance(error,ModelError) else {}}) from error


def commands():
    kinds = CREATE_KINDS
    fields = {f: OptionSpec('--' + f.replace('_', '-'), takes_value=True) for f in CREATE_FIELDS}
    result = []
    for name in BASIC_COMMANDS:
        example = {'--actor-type':'human', '--actor-id':'author'}
        extras, args, positional = [], {}, 'target'
        if name == 'artifact.create':
            extras = [*fields.values(), OptionSpec('--input',takes_value=True)]
            positional = 'artifact_type'; args[positional] = 'goal'
        elif name == 'artifact.update':
            extras = [OptionSpec('--input',takes_value=True,excludes=('--set','--unset')),
                OptionSpec('--set',takes_value=True,repeatable=True), OptionSpec('--unset',takes_value=True,repeatable=True)]
            example.update({'--set':['/title="Updated"'],'--expected-revision':'1'})
        elif name == 'lifecycle.transition':
            extras = [OptionSpec('--to',takes_value=True,required=True), OptionSpec('--reason',takes_value=True,required=True)]
            example.update({'--to':'proposed','--reason':'Explicit transition'})
        elif name == 'relation.add':
            positional = 'source'
            extras = [OptionSpec('--type',takes_value=True,required=True), OptionSpec('--target',takes_value=True,required=True),
                OptionSpec('--rationale',takes_value=True), OptionSpec('--position',takes_value=True)]
            example.update({'--type':'references','--target':'SR-GOAL-'+'0'*26})
        else:
            positional = 'source'
            extras = [OptionSpec('--relation-id',takes_value=True,required=True), OptionSpec('--reason',takes_value=True,required=True)]
            example.update({'--relation-id':'REL-'+'0'*26, '--reason':'Explicit removal','--expected-sha256':'0'*64})
        if name in ('artifact.update','lifecycle.transition','relation.remove'):
            extras += [OptionSpec('--expected-revision',takes_value=True)] if name != 'relation.remove' else []
            extras += [OptionSpec('--expected-sha256',takes_value=True,required=name == 'relation.remove')]
        args.setdefault(positional,'SR-GOAL-'+'0'*26)
        result.append(CommandSpec(name,tuple(name.split('.')),CommandClass.NORMATIVE_WRITE,
            PreflightProfile.PROJECT_WRITE,EffectScope.NORMATIVE_TRANSACTION,
            handler=command,requires_project=True,configuration_schema_required=True,
            aliases=(('create',),) if name == 'artifact.create' else (),
            positionals=(PositionalSpec(positional,choices=tuple(kinds) if name=='artifact.create' else ()),),
            options=common_options()+tuple(extras),
            protocol=CommandProtocol('native-authoring-command-v1', {'command_id':name,'arguments':args,'options':example},
                handler_exit_codes=tuple(range(8)),diagnostic_codes=('CORE_USAGE','CORE_MODEL','CORE_ENVIRONMENT','CORE_CONFLICT','CORE_SECURITY'),
                lock_kind='writer',work=WorkContract('native_project_authoring',('complete_history_inventory','full_target_qualification','native_writer')))))
    for name in SPECIAL_COMMANDS:
        positional = ()
        extra = (OptionSpec('--input', takes_value=True, required=name not in ('relation.review','baseline.create')),)
        if name == 'relation.review':
            positional = (PositionalSpec('source', required=False),)
            extra += tuple(OptionSpec('--'+flag, takes_value=True) for flag in
                ('relation-id','decision','reason','comment','expected-revision','expected-sha256'))
        elif name == 'baseline.create':
            positional = (PositionalSpec('name', required=False),)
            extra += (OptionSpec('--configuration', takes_value=True),OptionSpec('--release', takes_value=True))
        elif name == 'evidence.import':
            positional = (PositionalSpec('import_format',required=False,choices=('generic','junit','sarif')),
                PositionalSpec('source_path',required=False))
            extra += (OptionSpec('--run-context',takes_value=True),OptionSpec('--configuration',takes_value=True))
        elif name == 'evidence.record':
            positional = (PositionalSpec('verification_id', required=False),)
            extra += (OptionSpec('--run-context', takes_value=True),OptionSpec('--configuration', takes_value=True))
        result.append(CommandSpec(name,tuple(name.split('.')),CommandClass.NORMATIVE_WRITE,
            PreflightProfile.PROJECT_WRITE,EffectScope.NORMATIVE_TRANSACTION,
            handler=command,requires_project=True,configuration_schema_required=True,
            positionals=positional, options=common_options()+extra,
            protocol=CommandProtocol('native-authoring-command-v1', {'command_id':name,
                'options':{'--input':'intent.json','--actor-type':'human','--actor-id':'author'}},
                handler_exit_codes=tuple(range(8)),diagnostic_codes=('CORE_USAGE','CORE_MODEL','CORE_ENVIRONMENT','CORE_CONFLICT','CORE_SECURITY'),
                lock_kind='writer',work=WorkContract('native_project_authoring',
                    ('complete_history_inventory','explicit_specialist_input','full_target_qualification','native_writer')))))
    result.append(CommandSpec('change.apply',('change','apply'),CommandClass.NORMATIVE_WRITE,
        PreflightProfile.PROJECT_WRITE,EffectScope.NORMATIVE_TRANSACTION,
        handler=command,requires_project=True,configuration_schema_required=True,
        positionals=(PositionalSpec('plan_file'),),
        options=tuple(o for o in common_options() if o.flag not in ('--as-proposal','--proposal-input')),
        protocol=CommandProtocol('native-authoring-command-v1', {'command_id':'change.apply',
            'arguments':{'plan_file':'change-plan.json'},'options':{'--actor-type':'human','--actor-id':'author'}},
            handler_exit_codes=tuple(range(8)),diagnostic_codes=('CORE_USAGE','CORE_MODEL','CORE_ENVIRONMENT','CORE_CONFLICT','CORE_SECURITY', *known_codes()),
            lock_kind='writer',work=WorkContract('native_saved_authoring',('unchanged_plan','complete_inventory','native_writer')))))
    return tuple(result)
