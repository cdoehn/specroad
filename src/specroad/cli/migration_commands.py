"""Public fixed migration routes and explicit, versioned command effects."""
from .contracts import CommandClass, CommandProtocol, CommandSpec, EffectScope, PreflightProfile, WorkContract
from .parameters import OptionSpec

PLANNING = ('--inputs-root', '--inputs', '--actor-type', '--actor-id', '--planned-at', '--plan-id', '--request-id')
BOUND_PLAN = ('--plan-root', '--plan', '--expected-plan-sha256', '--expected-inputs-sha256')
BACKUP = ('--backup-root', '--backup')


def _handle(invocation):
    from .migration_command import migration_command
    return migration_command(invocation)


def migration_commands():
    from .commands import _read_runtime_options
    result = []
    for mode in ('plan', 'apply', 'verify'):
        flags = ['--project', '--to', '--work-dir']
        if mode in ('plan', 'apply'): flags += list(PLANNING)
        if mode != 'plan': flags += [*BOUND_PLAN, *BACKUP, '--transaction-id', '--expected-report-sha256']
        if mode == 'plan': flags += ['--output-root', '--output']
        if mode == 'verify': flags += ['--expected-backup-sha256']
        options = tuple(OptionSpec(flag, takes_value=True,
            choices=('human', 'tool', 'ai', 'ci') if flag == '--actor-type' else ()) for flag in flags)
        work = (WorkContract('native_migration_phase', ('original_source_bindings',), True,
            ('external_work_directory',), ('work-manifest-segments-v1',)) if mode != 'apply'
            else WorkContract('native_schema_transaction', ('bound_plan', 'verified_backup', 'host_authority')))
        example = {'--project': '/project', '--to': '0.2.0'}
        if mode == 'plan':
            example.update({'--inputs-root': '/inputs', '--inputs': 'mapping.json',
                '--actor-type': 'human', '--actor-id': 'author', '--planned-at': '2026-11-04T00:00:00Z',
                '--plan-id': 'CP-migration', '--output-root': '/output', '--output': 'migration.json'})
        else:
            example.update({'--plan-root': '/plans', '--plan': 'migration.json',
                '--expected-plan-sha256': 'a'*64, '--expected-inputs-sha256': 'b'*64,
                '--backup-root': '/backup', '--backup': 'source.zip', '--transaction-id': 'migration'})
            if mode == 'verify':
                example.update({'--expected-report-sha256': 'c'*64, '--expected-backup-sha256': 'd'*64})
        result.append(CommandSpec('migrate.' + mode, ('migrate', mode),
            CommandClass.PLAN_OUTPUT if mode == 'plan' else CommandClass.NORMATIVE_WRITE if mode == 'apply' else CommandClass.READ_ONLY,
            PreflightProfile.INPUT_READ,
            EffectScope.EXTERNAL_OUTPUT if mode == 'plan' else EffectScope.NORMATIVE_TRANSACTION if mode == 'apply' else EffectScope.NONE,
            handler=_handle, requires_project=True,
            options=(*options, *_read_runtime_options(),
                OptionSpec('--format', takes_value=True, choices=('pretty', 'json')), OptionSpec('--quiet'), OptionSpec('--no-color')),
            budget_policy_version='runtime-budget-v2',
            protocol=CommandProtocol('migration-command-v1', {'command_id': 'migrate.' + mode, 'options': example},
                handler_exit_codes=(0,2,3,4,5,6,7,8) if mode != 'apply' else (0,2,3,4,5,6,7),
                diagnostic_codes=('CORE_USAGE','CORE_MODEL','CORE_ENVIRONMENT','CORE_CONFLICT','CORE_SECURITY'),
                lock_kind='writer' if mode == 'apply' else 'none', work=work)))
    return tuple(result)
