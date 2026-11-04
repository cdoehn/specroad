"""Explicit synthetic host registration; no serialized handler or authority."""
from specroad.cli.contracts import CommandSpec, CommandClass, PreflightProfile, EffectScope
from specroad.cli.registry import CommandRegistry
from specroad.cli.requests import CommandRequest
from specroad.security import ProjectBoundary
from specroad.work.checkpoints import CheckpointStore
from specroad.work.root import WorkDirectory
from specroad.work.migration import prepare_migration_planning_work, prepare_migration_verification_work


def registry():
    def forbidden(invocation):
        raise AssertionError('Work must execute native phases, never dispatch a stored handler')
    return CommandRegistry(tuple(CommandSpec('migrate.' + name, ('migrate', name),
        CommandClass.PLAN_OUTPUT if name == 'plan' else CommandClass.READ_ONLY,
        PreflightProfile.INPUT_READ,
        EffectScope.EXTERNAL_OUTPUT if name == 'plan' else EffectScope.NONE,
        handler=forbidden) for name in ('plan', 'verify')))


def create(data, directory, *, mode='plan'):
    host = registry(); root, source, plan, args, backup, report, target, bindings = data
    request = CommandRequest('migrate.' + mode)
    if mode == 'plan':
        value = plan.data
        initial = prepare_migration_planning_work(host, request, backup,
            expected_backup_sha256=bindings['expected_backup_sha256'],
            expected_source_files_sha256=bindings['expected_source_files_sha256'],
            inputs=value['operations'][0]['inputs'], target_version='0.2.0',
            **{key: value[key] for key in ('actor','planned_at','change_plan_id','request_id')})
    else:
        initial = prepare_migration_verification_work(host, request, backup,
            plan.source_bytes, report.canonical_bytes, target, **bindings)
    location = WorkDirectory(initial, protected_roots=(ProjectBoundary(root),), directory=directory)
    store = CheckpointStore(location, initial)
    store.publish(initial)
    return store


def finish(store, *, gates=()):
    from specroad.work.migration import resume_migration_work
    # The fixed phase list has three real phases and one durable completion.
    for _ in range(4):
        if store.read().as_dict()['state'] == 'completed': break
        resume_migration_work(store, gates=gates)
    assert store.read().as_dict()['state'] == 'completed'


def publication(data):
    return {key: data[3][key] for key in ('transaction_id', 'backup_path', 'backup_root', 'authority')}
