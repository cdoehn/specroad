"""Explicit target inputs and native contract binding; no host defaults."""
from ..storage.json_syntax import parse_json_object as parsed
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.configuration import ProjectConfiguration
from ..model.model_manifest import ProjectReadBinding, ManifestResource
from ..model.manifest_resources import project_json_resource
from ..model.language_registry import LanguageRegistry
from ..model.language_package_values import LanguagePackage
from ..profiles.values import ProfileResource
from ..profiles.composition import compose_profiles
from .plan_values import require, owned_files, b64, unb64, MANIFEST_PATH
from .plan_contract import validate_inputs
from .requirement_mapping import materialize_language_default


def migration_inputs(*, target_configuration=None, target_resources=None,
                     requirement_mappings=(), proposal_mappings=(),
                     requirement_default_language=None):
    """Materialize authored mappings, without inferring text, force or language.

    Only an explicitly supplied language default fills an absent language key.
    Every requirement still needs its own source hash, force and complete text.
    The normalized, detached v1 value binds each resulting decision individually;
    supplying it is neither a human review nor authorization to apply a plan.
    """
    require(target_configuration is None or type(target_configuration) is bytes,
            'migration_configuration_bytes_required')
    resources = owned_files({} if target_resources is None else target_resources)
    sequences = []
    for rows in (requirement_mappings, proposal_mappings):
        require(type(rows) in (tuple, list) and all(type(r) is dict and
            type(r.get('artifact_id')) is str for r in rows), 'migration_mapping_required')
        sequences.append(sorted((dict(row) for row in rows),
                                key=lambda r: r['artifact_id'].encode('utf-8')))
    materialize_language_default(sequences[0], requirement_default_language)
    value = {'format_version': 'migration-inputs-v1',
        'target_configuration': None if target_configuration is None else b64(target_configuration),
        'target_resources': [{'path': p, 'bytes_base64': b64(b)} for p, b in sorted(resources.items())],
        'requirement_mappings': sequences[0], 'proposal_mappings': sequences[1]}
    value = parsed(jcs(value)); validate_inputs(value)
    return value


def _builtin_core():
    from importlib import resources
    return ProfileResource(resources.files("specroad.profile_data").joinpath("core.json").read_bytes())


def target_contract():
    """Bind actual compiled schema values, not a mutable project version label."""
    from ..model.domain_schemas import DOMAIN_TYPES, domain_schema
    from ..model.record_schemas import RECORD_TYPES, record_schema
    from ..model.configuration_schema import configuration_json_schema
    from ..changes.schema import change_plan_schema
    schemas = {kind: domain_schema(kind) for kind in DOMAIN_TYPES}
    schemas.update({kind: record_schema(kind) for kind in RECORD_TYPES})
    schemas.update(project=configuration_json_schema(), profile=_builtin_core().data, change_plan=change_plan_schema())
    return {'schema_version': '0.2.0', 'contract_sha256': digest({
        'contract_version': 'migration-target-v1', 'schemas': schemas})}


def _target(inputs, project_id, prefix):
    blockers = []
    if inputs['target_configuration'] is None:
        blockers.append({'reason': 'target_configuration_required', 'path': 'specroad.json'})
        return None, blockers
    raw = unb64(inputs['target_configuration']); config = ProjectConfiguration(parsed(raw))
    require(config.project_id == project_id and config.id_prefix == prefix, 'migration_project_mismatch')
    files = owned_files({r['path']: unb64(r['bytes_base64']) for r in inputs['target_resources']})
    binding = ProjectReadBinding(project_id, 'owned-migration-input', (0, 0))
    records, profiles, packages, registry = [], [], [], None
    registry_binding = config.data.get('language_registry')
    for path, content in files.items():
        require(path.startswith(('profiles/', 'rules/', 'mappings/')) and path != MANIFEST_PATH,
                'migration_target_resource_forbidden', path=path)
        if registry_binding and path == registry_binding['path']:
            registry = LanguageRegistry(content, expected_sha256=registry_binding['sha256'],
                                        expected_version=registry_binding['registry_version'])
            records.append(ManifestResource(binding, {'kind': 'language_registry', 'path': path,
                'id': registry_binding['registry_id'], 'version': registry.version,
                'size': len(content), 'sha256': registry.sha256}))
        elif path.startswith('profiles/language-data/'):
            packages.append(LanguagePackage(content))
        else:
            records.append(project_json_resource(config, path, content, binding))
            if path.startswith('profiles/'):
                profiles.append(ProfileResource(content))
    if registry_binding and registry is None:
        blockers.append({'reason': 'target_language_registry_required', 'path': registry_binding['path']})
    core = [p for p in profiles if p.profile_id == 'core']
    require(len(core) <= 1, 'migration_target_core_conflict')
    if not core:
        blockers.append({'reason': 'target_core_profile_required', 'path': 'profiles/'})
    if core:
        require(core[0].sha256 == _builtin_core().sha256, 'migration_target_core_not_builtin')
    available = {p.key for p in profiles}
    for key in config.data['profiles']:
        if key not in available: blockers.append({'reason': 'target_profile_required', 'path': key})
    package_by_key = {p.key: p for p in packages}
    require(len(package_by_key) == len(packages), 'migration_target_package_conflict')
    for key in config.data.get('language_packages', []):
        if key not in package_by_key: blockers.append({'reason': 'target_language_package_required', 'path': key})
    require(set(package_by_key) <= set(config.data.get('language_packages', [])), 'migration_unselected_language_package')
    if blockers:
        return None, blockers
    effective = compose_profiles(profiles, core_key=core[0].key,
        project_profiles=[key for key in config.data['profiles'] if key != core[0].key],
        language_registry=registry,
        language_packages=[package_by_key[k] for k in config.data.get('language_packages', [])])
    return {'configuration': config, 'configuration_bytes': raw, 'files': files,
        'binding': binding, 'resources': records, 'profile': effective, 'registry': registry}, []
