"""A real minimal project for commands whose declared input includes a root."""
from contextlib import contextmanager

from specroad.changes.target_model import TargetModel
from specroad.model.canonical import canonical_json_bytes
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.paths import artifact_path
from specroad.profiles import ProfileResource, compose_profiles
from specroad.storage.language_registry import bundled_language_registry, registry_binding
from specroad.validation import ModelDocument
from .domain import domain_value
from .model import configuration_value, put
from .profiles import profile_data


def inspection_project(root, *, artifacts=None, extra_profiles=()):
    root.mkdir(exist_ok=True)
    registry = bundled_language_registry()
    profile = ProfileResource(canonical_json_bytes(profile_data(profile_id='core')))
    resources = [profile, *extra_profiles]
    keys = [p.key for p in extra_profiles]
    configuration = configuration_value(language_registry=registry_binding(registry), profiles=keys,
                                        resource_limits={'trace_depth': 10})
    effective = compose_profiles(resources, core_key=profile.key, cli_profiles=keys, language_registry=registry)
    values = [domain_value('goal')] if artifacts is None else artifacts
    info = root.stat()
    model = TargetModel(canonical_json_bytes(configuration),
        ProjectReadBinding(configuration['project_id'], str(root), (info.st_dev, info.st_ino)),
        [ModelDocument(artifact_path(v['artifact_type'], v['id'], 'SR'), canonical_json_bytes(v)) for v in values],
        profile=effective, resource_files=[ModelDocument('profiles/' + p.profile_id + '.json', p.source_bytes)
            for p in resources] + [ModelDocument(registry_binding(registry)['path'], registry.source_bytes)])
    for path, raw in model.source_files.items():
        put(root, path, raw)
    (root / '.specroad/locks').mkdir(parents=True)
    return model


def command_example_project(root, command_id):
    """Supply the real semantic inputs required by each published example."""
    if command_id == 'configuration.evaluate':
        from .records import record_value
        return inspection_project(root, artifacts=[record_value('configuration')])
    if command_id in ('render', 'view.render'):
        from .records import record_value
        from .targets import SCOPE
        return inspection_project(root, artifacts=[record_value('document')] if command_id == 'render' else
            [record_value('view', scope_descriptor=SCOPE, columns=[{
                'source': {'kind': 'artifact_field', 'pointer': '/id'}, 'heading': 'ID',
                'data_type': 'string', 'format': 'plain', 'missing': 'error'}],
                relation_projections=[], grouping=[], sort=[])])
    if command_id == 'diagram':
        return inspection_project(root, artifacts=[domain_value('requirement')])
    if command_id == 'validate':
        from specroad.bundles import prepare_partial_bundle
        from specroad.bundles.extraction import extract_bundle
        from specroad.graph.scope_descriptors import ScopeDescriptor
        from .scopes import descriptor
        origin = root / 'origin'
        release = domain_value('release')
        inspection_project(origin, artifacts=[release])
        bundle = prepare_partial_bundle(origin, ScopeDescriptor(descriptor('release',
            {'release_id': release['id']}, boundary_policy='partial')))
        target = root / 'selected'
        extract_bundle(bundle.source_bytes, target)
        # The example discovers root; publish only the actual extracted fixture files.
        import shutil
        for path in target.iterdir():
            shutil.move(str(path), root / path.name)
        shutil.rmtree(origin); target.rmdir()
        return None
    if command_id == 'export':
        model = inspection_project(root)
        put(root, 'mappings/export.json', canonical_json_bytes({
            'schema_version': '0.2.0', 'mapping_format_version': 'exchange-mapping-v1',
            'mapping_id': 'example:export', 'mapping_version': '1.0.0', 'source_format': 'ndjson',
            'types': [], 'fields': [], 'relations': [], 'hierarchies': [], 'extensions': {}}))
        return model
    return inspection_project(root)


@contextmanager
def command_example_inputs(root, command):
    """Bind published path placeholders to real native inputs under this root.

    The Work fixture labels its synthetic build identity explicitly. No native
    model/recovery/checkpoint validator or command handler is replaced.
    """
    if command.command_id == 'recover.restore' or command.command_id.startswith('work.'):
        from unittest.mock import patch
        from specroad import _build
        # Development modules are deliberately unrecorded; a native Work
        # container requires an explicit compatible build identity.
        with patch.object(_build, 'BUILD_METADATA', {'format_version': 1,
                'hash_algorithm': 'specroad-dev-payload-v1', 'build_sha256': '4' * 64}):
            yield _restore_example_inputs(root, command)
        return
    if command.requires_project:
        command_example_project(root, command.command_id)
    elif command.command_id in ('bundle.verify', 'bundle.extract'):
        from specroad.bundles import prepare_project_bundle
        origin = root / 'origin'
        inspection_project(origin)
        put(root, 'project.zip', prepare_project_bundle(origin).source_bytes)
    yield command.protocol.example.as_dict()


def _restore_example_inputs(root, command):
    from specroad.cli.commands import builtin_registry
    from specroad.cli.requests import CommandRequest
    from specroad.work.checkpoints import CheckpointStore
    from specroad.work.open_existing import protected_paths
    from specroad.work.restore_planning import prepare_planning_work
    from specroad.work.root import WorkDirectory
    from .restore import restore_case, plan_for

    options, _, _ = restore_case(root)
    output = root / 'output'; output.mkdir()
    planning = {'--project': str(options['project_root']), '--source-root': str(options['source_root']),
        '--from': options['source_path'], '--source-kind': 'project_bundle', '--dry-run': True,
        '--output-root': str(output), '--output': 'restore.json'}
    request = command.protocol.example.as_dict()
    if command.command_id == 'recover.restore':
        request['options'] = {**request['options'], **planning}
        return request

    registry = builtin_registry()
    if command.command_id == 'work.resume':
        from specroad.changes.recovery_values import RecoveryAuthority
        from specroad.work.restore_execution import prepare_restore_work
        from specroad.work.restore_progress import resume_restore_work
        plan = plan_for(options)
        actor = {'actor_type': 'human', 'actor_id': 'synthetic-example-host'}
        original = CommandRequest('recover.restore', {'--project': str(options['project_root']),
            '--plan-root': str(output), '--plan': 'restore.json',
            '--expected-target-root': plan.data['expected_target_root'],
            '--actor-type': actor['actor_type'], '--actor-id': actor['actor_id']})
        put(output, 'restore.json', plan.source_bytes)
        initial = prepare_restore_work(registry, original, plan=plan)
    else:
        initial = prepare_planning_work(registry, CommandRequest('recover.restore', planning))
    location = WorkDirectory(initial, protected_roots=(), protected_paths=protected_paths(initial),
                             directory=root / 'work')
    store = CheckpointStore(location, initial); store.publish(initial)
    if command.command_id == 'work.resume':
        # A finished native operation is the minimal successful no-authority
        # resume example; active execution still requires a fresh host grant.
        resume_restore_work(store, registry=registry, actor=actor,
            authority=RecoveryAuthority('synthetic-example-host', '1', lambda request: True))
    if command.command_id == 'work.restore':
        from specroad.work.package_publication import publish_work_package
        transport = root / 'transport'; transport.mkdir()
        publish_work_package(store, output_root=transport, output='work.zip')
        request['arguments']['file'] = str(transport / 'work.zip')
        request['options']['--output'] = str(root / 'relocated')
    else:
        request['arguments']['work_dir'] = str(location.path)
        if command.command_id == 'work.export':
            transport = root / 'transport'; transport.mkdir()
            request['options']['--output'] = str(transport / 'work.zip')
    return request
