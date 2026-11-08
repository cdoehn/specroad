"""Read-only conflict inspection; stored inputs never authorize a merge."""
from pathlib import Path

from .contracts import CommandSpec, CommandClass, PreflightProfile, EffectScope, CommandProtocol
from .parameters import OptionSpec, PositionalSpec
from .results import CommandResult, FailureKind, OperationFailure


def conflict_command_schema():
    from ..merge.conflict_schema import object_schema, schema
    from ..merge.resolution_schema import schema as resolution_schema
    return object_schema({'format_version':{'const':'merge-conflicts-command-v1'},
        'source_validation':{'const':'not_revalidated'},
        'plan_sha256':{'type':'string','pattern':r'^[0-9a-f]{64}(?![\s\S])'},
        'plan':{'anyOf': [schema(), resolution_schema()]}})


def resolve_command_schema():
    from ..merge.conflict_schema import object_schema
    from ..merge.resolution_schema import schema
    return object_schema({'format_version': {'const': 'merge-resolve-command-v1'},
        'source_validation': {'const': 'revalidated'},
        'plan_sha256': {'type': 'string', 'pattern': r'^[0-9a-f]{64}(?![\s\S])'},
        'plan': schema()})


def merge_resolve_command(invocation):
    from .merge_resolution import resolve_command
    return resolve_command(invocation)


def merge_conflicts_command(invocation):
    # Registry construction must preserve project-free bootstrap commands.
    from ..model.errors import ModelError
    from ..security import ProjectBoundary, SafetyViolation
    from ..merge.resolutions import parse_resolution_plan
    try:
        path = Path(invocation.arguments['merge_plan']).absolute()
        bound = ProjectBoundary(path.parent)
        if bound.root != path.parent:
            raise SafetyViolation('Canonical plan parent required')
        raw = bound.read_bytes(path.name)
        plan = parse_resolution_plan(raw)
        if bound.read_bytes(path.name) != raw:
            raise SafetyViolation('Plan changed during inspection')
        return CommandResult('merge.conflicts', result={
            'format_version':'merge-conflicts-command-v1','source_validation':'not_revalidated',
            'plan_sha256':plan.sha256,'plan':plan.data})
    except ModelError as error:
        raise OperationFailure(FailureKind.MODEL, error.reason) from error
    except SafetyViolation as error:
        raise OperationFailure(FailureKind.SECURITY, str(error)) from error


def merge_commands():
    return (planning_spec(), apply_spec(), CommandSpec('merge.conflicts', ('merge','conflicts'), CommandClass.READ_ONLY,
        PreflightProfile.INPUT_READ, EffectScope.NONE, handler=merge_conflicts_command,
        positionals=(PositionalSpec('merge_plan'),),
        options=(OptionSpec('--format',takes_value=True,choices=('pretty','json')),
                 OptionSpec('--quiet'),OptionSpec('--no-color')),
        protocol=CommandProtocol('merge-conflicts-command-v1', {'command_id':'merge.conflicts',
            'arguments':{'merge_plan':'/plans/merge.json'},'options':{'--format':'json'}},
            handler_exit_codes=(0,2,3,4,5,7),
            diagnostic_codes=('CORE_USAGE','CORE_MODEL','CORE_ENVIRONMENT','CORE_SECURITY'))),
        CommandSpec('merge.resolve', ('merge','resolve'), CommandClass.PLAN_OUTPUT,
        PreflightProfile.INPUT_READ, EffectScope.EXTERNAL_OUTPUT, handler=merge_resolve_command,
        positionals=(PositionalSpec('merge_plan'),),
        options=(OptionSpec('--conflict', takes_value=True, required=True),
                 OptionSpec('--take', takes_value=True, choices=('ours','theirs','base'), excludes=('--value',)),
                 OptionSpec('--value', takes_value=True, excludes=('--take',)),
                 OptionSpec('--inputs', takes_value=True, required=True),
                 OptionSpec('--expected-plan-sha256', takes_value=True, required=True),
                 OptionSpec('--actor-type', takes_value=True, required=True, choices=('human','ai','ci','tool')),
                 OptionSpec('--actor-id', takes_value=True, required=True),
                 OptionSpec('--resolved-at', takes_value=True, required=True),
                 OptionSpec('--format',takes_value=True,choices=('pretty','json')),
                 OptionSpec('--quiet'),OptionSpec('--no-color')),
        protocol=CommandProtocol('merge-resolve-command-v1', {'command_id':'merge.resolve',
            'arguments':{'merge_plan':'/plans/merge.json'}, 'options':{'--format':'json',
                '--conflict':'MC-'+'0'*64, '--take':'ours', '--inputs':'/plans/inputs.json',
                '--expected-plan-sha256':'0'*64, '--actor-type':'human',
                '--actor-id':'example-operator', '--resolved-at':'2026-01-01T00:00:00Z'}},
            handler_exit_codes=(0,2,3,4,5,7),
            diagnostic_codes=('CORE_USAGE','CORE_MODEL','CORE_ENVIRONMENT','CORE_SECURITY'))))


def merge_planning_command(invocation):
    from .merge_planning import planning_command
    return planning_command(invocation)

def planning_spec():
    from .contracts import CommandClass, CommandProtocol, CommandSpec, EffectScope, PreflightProfile, WorkContract
    from .parameters import OptionSpec
    from .commands import _read_runtime_options
    options = []
    for role in ('base', 'ours', 'theirs'):
        options.extend((OptionSpec('--'+role, takes_value=True),
                        OptionSpec('--'+role+'-kind', takes_value=True, choices=('local', 'git', 'baseline', 'bundle')),
                        OptionSpec('--'+role+'-ref', takes_value=True)))
    options.extend(OptionSpec(flag, takes_value=True) for flag in
        ('--history', '--plan-id', '--resolutions', '--expected-plan-sha256', '--work-dir',
         '--project', '--change-plan-id', '--actor-id', '--planned-at', '--request-id'))
    options.extend((OptionSpec('--for-apply'), OptionSpec('--actor-type', takes_value=True,
                    choices=('human', 'tool', 'ai', 'ci'))))
    return CommandSpec('merge.plan', ('merge', 'plan'), CommandClass.PLAN_OUTPUT,
        PreflightProfile.INPUT_READ, EffectScope.EXTERNAL_OUTPUT, handler=merge_planning_command,
        options=(*options, *_read_runtime_options(), OptionSpec('--fail-on-change'),
                 OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
                 OptionSpec('--quiet'), OptionSpec('--no-color')),
        budget_policy_version='runtime-budget-v2',
        protocol=CommandProtocol('merge-plan-command-v1', {'command_id': 'merge.plan', 'options': {
            '--base': '/base', '--ours': '/ours', '--theirs': '/theirs', '--history': '/inputs/history.json',
            '--plan-id': 'MP-00000000000000000000000000'}}, handler_exit_codes=tuple(range(9)),
            diagnostic_codes=('CORE_USAGE', 'CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_CONFLICT', 'CORE_SECURITY'),
            work=WorkContract('native_merge_phase', ('sealed_source_bindings',), True,
                              ('external_work_directory',), ('work-manifest-segments-v1',))))


def merge_apply_command(invocation):
    from .merge_apply import apply_command
    return apply_command(invocation)


def apply_spec():
    from .contracts import WorkContract
    options = [OptionSpec('--project', takes_value=True, required=True),
               OptionSpec('--expected-plan-sha256', takes_value=True, required=True), OptionSpec('--dry-run')]
    for role in ('base', 'ours', 'theirs'):
        options.extend((OptionSpec('--'+role, takes_value=True),
            OptionSpec('--'+role+'-kind', takes_value=True, choices=('local', 'git', 'baseline', 'bundle')),
            OptionSpec('--'+role+'-ref', takes_value=True)))
    options.extend(OptionSpec(flag, takes_value=True) for flag in ('--backup-root', '--backup', '--transaction-id'))
    return CommandSpec('merge.apply', ('merge', 'apply'), CommandClass.NORMATIVE_WRITE,
        PreflightProfile.INPUT_READ, EffectScope.NORMATIVE_TRANSACTION, handler=merge_apply_command,
        requires_project=True, positionals=(PositionalSpec('merge_plan'),), options=(*options,
            OptionSpec('--format', takes_value=True, choices=('pretty', 'json')), OptionSpec('--quiet'), OptionSpec('--no-color')),
        protocol=CommandProtocol('merge-apply-command-v1', {'command_id': 'merge.apply',
            'arguments': {'merge_plan': '/plans/merge-publication.json'}, 'options': {
                '--project': '/ours', '--expected-plan-sha256': 'a'*64, '--base': '/base', '--ours': '/ours',
                '--theirs': '/theirs', '--backup-root': '/backup', '--backup': 'source.zip', '--transaction-id': 'merge'}},
            handler_exit_codes=(0,2,3,4,5,6,7),
            diagnostic_codes=('CORE_USAGE','CORE_MODEL','CORE_ENVIRONMENT','CORE_CONFLICT','CORE_SECURITY'),
            lock_kind='writer', work=WorkContract('native_schema_transaction', ('bound_plan', 'verified_backup', 'host_authority'))))
