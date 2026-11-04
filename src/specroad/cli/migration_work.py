"""Public passive migration Work; write authority is always supplied afresh."""
from hashlib import sha256
from contextlib import nullcontext
from ..cli.requests import CommandRequest
from ..model.canonical import canonical_json_bytes as jcs
from ..changes.values import ChangePlan
from ..migration.plan_values import require, file_bindings
from ..bundles.migration_source import prepare_source_backup
from ..migration._backup_source import _observe
from ..security import ProjectBoundary
from ..work.root import WorkDirectory
from ..work.checkpoints import CheckpointStore
from ..work._public_errors import work_errors
from ..work.migration import (prepare_migration_planning_work, prepare_migration_verification_work,
    resume_migration_work, migration_work_result, _inputs, _calculate)


def checked(current, *, gates=()):
    _, _, tasks, done = _inputs(current)
    _calculate(current, len(done), gates=gates)


def _start(invocation, root, options, initial):
    from .work_handler import continuation
    protected = [ProjectBoundary(root)]
    for flag in ('--inputs-root', '--plan-root', '--backup-root', '--output-root'):
        if flag in options:
            protected.append(ProjectBoundary(options[flag]))
    location = WorkDirectory(initial, protected_roots=tuple(protected), directory=options.get('--work-dir'))
    store = CheckpointStore(location, initial)
    store.publish(initial)
    current = resume_migration_work(store, gates=invocation.migration_gates)
    return continuation(invocation.command.command_id, store, current, migration_gates=invocation.migration_gates)


@work_errors
def start_planning(invocation, root, options, files, planning, current):
    backup = prepare_source_backup(files)
    initial = prepare_migration_planning_work(invocation.registry, CommandRequest('migrate.plan'),
        backup.source_bytes, expected_backup_sha256=backup.sha256,
        expected_source_files_sha256=backup.manifest['source_files_sha256'], **planning)
    current()
    return _start(invocation, root, options, initial)


@work_errors
def start_verification(invocation, root, options, backup, plan, report, observation, bindings):
    files, _, current = _observe(root)
    value = observation.data
    expected = value['target_files'] + value['operational_evidence']['files']
    require(sorted(expected,key=lambda r:r['path']) == file_bindings(files),
            'migration_verification_target_changed', exit_code=6)
    target = {r['path']:files[r['path']] for r in value['target_files']}
    initial = prepare_migration_verification_work(invocation.registry, CommandRequest('migrate.verify'),
        backup, plan.source_bytes, report, target, **bindings)
    current()
    return _start(invocation, root, options, initial)


@work_errors
def completed_plan(invocation, options):
    from ..work.open_existing import open_restore_work
    from .migration_command import _required
    _required(options,'--expected-plan-sha256','--expected-inputs-sha256')
    store = open_restore_work(options['--work-dir'], registry=invocation.registry)
    result = migration_work_result(store, gates=invocation.migration_gates)
    require(result['command_id'] == 'migrate.plan', 'migration_work_planning_required', exit_code=6)
    report = result['planning']; plan = ChangePlan(jcs(report['change_plan']))
    require(plan.sha256 == options['--expected-plan-sha256'] and report['inputs_sha256'] == options['--expected-inputs-sha256'],
            'migration_execution_binding_changed', exit_code=6)
    def current():
        require(migration_work_result(store, gates=invocation.migration_gates) == result,
                'migration_work_result_changed', exit_code=6)
    return report, plan, current


def work_command(invocation, store, operation):
    from .work_handler import _payload, continuation, absolute
    from ..work.resume import _runtime_build
    require(not any(k in invocation.options for k in ('--force','--expected-lock-sha256',
        '--accept-remote-risk','--expected-work-lock-sha256','--work-recovery-reason','--project')),
        'migration_work_passive_options_required', exit_code=2)
    if operation == 'export':
        from ..work.package_publication import publish_work_package
        checked(store.read(), gates=invocation.migration_gates)
        path = absolute(invocation.options['--output'])
        return _payload(operation,publish_work_package(store,output_root=path.parent,output=path.name))
    if operation == 'cancel':
        from ..work.control import _cancel
        return _payload(operation,_cancel(store,invocation.options['--reason'],_runtime_build(),
            lambda current: checked(current,gates=invocation.migration_gates),lambda current:nullcontext()))
    require(operation == 'resume', 'migration_work_operation_invalid', exit_code=2)
    current = resume_migration_work(store,gates=invocation.migration_gates)
    if current.as_dict()['state'] != 'completed':
        return continuation('work.resume',store,current,migration_gates=invocation.migration_gates)
    return _payload(operation,migration_work_result(store,gates=invocation.migration_gates))
