"""A real minimal project for commands whose declared input includes a root."""
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
    if command_id == 'export':
        model = inspection_project(root)
        put(root, 'mappings/export.json', canonical_json_bytes({
            'schema_version': '0.2.0', 'mapping_format_version': 'exchange-mapping-v1',
            'mapping_id': 'example:export', 'mapping_version': '1.0.0', 'source_format': 'ndjson',
            'types': [], 'fields': [], 'relations': [], 'hierarchies': [], 'extensions': {}}))
        return model
    return inspection_project(root)
