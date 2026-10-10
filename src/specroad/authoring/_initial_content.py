"""Prepare an owned minimum project from validated distribution resources."""
from datetime import datetime, timezone
from uuid import uuid4

from ..model.artifact_types import artifact_types
from ..model.canonical import canonical_json_bytes
from ..model.configuration import ProjectConfiguration
from ..model.identities import IdentityInventory, allocate_artifact_identity
from ..model.language_policy import resolve_language_policy
from ..model.paths import artifact_path
from ..profiles.composition import compose_profiles
from ..storage.language_packages import bundled_package_index, load_bundled_package
from ..storage.language_registry import bundled_language_registry, registry_binding
from ..storage.profiles import load_bundled_profile
from ..storage.record_artifact import RecordArtifact

ROOT_DIRECTORIES = ('spec', 'profiles', 'rules', 'mappings', 'attachments',
                    'archive', 'generated', '.specroad')


def distribution_content():
    """Validated release resources, without allocating new project identities."""
    registry = bundled_language_registry()
    profiles = tuple(load_bundled_profile(key) for key in
                     ('core@0.2.0', 'software-de@0.2.0', 'software-en@0.2.0'))
    compose_profiles(profiles, core_key='core@0.2.0', project_profiles=('software-de@0.2.0',))
    packages = tuple(load_bundled_package(p['package_id'] + '@' + p['version'])
                     for p in bundled_package_index())
    content = {registry_binding(registry)['path']: registry.source_bytes}
    for profile in profiles:
        content['profiles/' + profile.profile_id + '.json'] = profile.source_bytes
    for package in packages:
        content['profiles/language-data/packages/' + package.package_id + '.json'] = package.source_bytes
    return registry, profiles, packages, content


def initial_directories():
    directories = set(ROOT_DIRECTORIES)
    directories.update('spec/' + item.directory for item in artifact_types())
    directories.update(('archive/objects', 'profiles/language-data', 'profiles/language-data/packages',
        '.specroad/cache', '.specroad/locks', '.specroad/tmp', '.specroad/transactions',
        '.specroad/transactions/receipts', '.specroad/requests', '.specroad/merge', '.specroad/recovery'))
    return directories


def project_configuration(project_name, project_id, registry, packages):
    return ProjectConfiguration({
        'schema_version': '0.2.0', 'project_id': project_id,
        'project_name': project_name, 'id_prefix': 'SR', 'default_locale': 'de-DE',
        'managed_paths': ['spec', 'profiles', 'rules', 'mappings', 'attachments', 'archive'],
        'profiles': ['core@0.2.0', 'software-de@0.2.0'], 'generated_path': 'generated',
        'validation_policy': {'fail_on': 'error', 'minimum_human_proposal_approvals': 1,
                              'required_relation_review': 'current'},
        'transaction_policy': {'auto_recover': True, 'retain_receipts': True},
        'language_policy': resolve_language_policy({}),
        'language_registry': registry_binding(registry),
        'language_packages': [p.key for p in packages],
        'srx_policy': {'numeric_policy_version': 'srx-decimal-v1', 'decimal_precision': 34},
    })


def primary_document(project_name, identity, now):
    actor = {'actor_type': 'tool', 'actor_id': 'specroad.init'}
    return {'schema_version': '0.2.0', 'id': identity.id, 'id_scheme': identity.id_scheme,
        'artifact_type': 'document', 'title': project_name, 'maturity': 'draft', 'revision': 1,
        'created_at': now, 'updated_at': now, 'created_by': actor, 'updated_by': actor,
        'relations': [], 'extensions': {}, 'purpose': 'Project specification',
        'audience': 'Project participants', 'language': 'de-DE',
        'document_role': 'primary_specification', 'render_policy': {}}


def initial_content(project_name):
    """No target access, writes, project imports or online resource resolution."""
    registry, profiles, packages, content = distribution_content()
    configuration = project_configuration(project_name, str(uuid4()), registry, packages)
    identity = allocate_artifact_identity('document', IdentityInventory('SR', (), (), ())).identity
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    document = primary_document(project_name, identity, now)
    path = artifact_path('document', identity.id, 'SR')
    raw = canonical_json_bytes(document)
    RecordArtifact(raw, expected_type='document', path=path)
    content.update({'specroad.json': canonical_json_bytes(configuration.data), path: raw})
    return content, initial_directories(), configuration, identity.id
