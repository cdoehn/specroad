"""Materialized fields and shared current/legacy manifest projection only."""
from hashlib import sha256
from ..storage.json_syntax import parse_json_object as parsed
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.model_manifest import ManifestResource, assemble_model_manifest
from ..changes._common import _artifact
from ..changes.metadata_time import next_update_time
from ..profiles.composition import check_composed_fields
from .plan_values import require, MigrationPlanError


def _target_fields(value, target):
    _artifact(value, '/target')
    result = check_composed_fields(target['profile'], value)
    require(result['field_checks_passed'], 'migration_target_profile_fields')
    if 'language' in value:
        from ..model.language_tags import parse_language_tag
        from ..model.language_policy import resolve_language_policy
        from ..model._language_package_parser import range_matches
        language = parse_language_tag(value['language'])
        policy = resolve_language_policy(target['configuration'].data.get('language_policy', {}))
        require(not language.unspecified or policy['unspecified_language'] != 'error', 'migration_target_language_policy')
        allowed = any(range_matches(r, value['language']) for r in policy['allowed_ranges'])
        require(allowed or policy['disallowed_language'] != 'error', 'migration_target_language_policy')
        registry = target['registry']
        if registry is not None:
            observation = registry.inspect(value['language'])
            require(observation.syntax_valid and (not observation.unknown_subtags or policy['unverified_registry'] != 'error'),
                    'migration_target_language_registry')
        elif policy['unverified_registry'] == 'error':
            raise MigrationPlanError('migration_target_language_registry')


def _stamp(original, actor, planned_at):
    value = parsed(jcs(original))
    value.update(schema_version='0.2.0', id_scheme='legacy-sequential-v1',
        revision=int(original['revision']) + 1, updated_by=actor,
        updated_at=next_update_time(planned_at, original['updated_at']))
    if value['maturity'] == 'approved':
        value['maturity'] = 'draft'
    return value


def _manifest(target, artifacts, legacy, legacy_hash, archives, inventory, descriptor):
    binding = target['binding']; resources = list(target['resources'])
    resources.append(ManifestResource(binding, {'kind': 'mapping', 'id': 'legacy-preservation',
        'version': '1.0.0', 'sha256': legacy_hash}))
    for path, raw in sorted(archives.items()):
        if path.startswith('archive/objects/'):
            resources.append(ManifestResource(binding, {'kind': 'archive', 'path': path,
                'size': len(raw), 'sha256': sha256(raw).hexdigest()}))
    for row in inventory.data['entries']:
        if row['role'] == 'attachment' and row['path'].startswith('attachments/'):
            resources.append(ManifestResource(binding, {'kind': 'attachment', 'path': row['path'],
                'size': row['size'], 'sha256': row['byte_sha256'], 'media_type': row['media_type']}))
    for value in artifacts:
        if descriptor['scope_kind'] == 'specification' and value['artifact_type'] in ('proposal', 'baseline'):
            continue
        resources.append(ManifestResource(binding, {'kind': 'artifact', 'id': value['id'],
            'artifact_type': value['artifact_type'], 'revision': int(value['revision']), 'sha256': digest(value)}))
    for original in legacy:
        value = original.data
        if descriptor['scope_kind'] == 'specification' and value['artifact_type'] in ('proposal', 'baseline'):
            continue
        resources.append(ManifestResource(binding, {'kind': 'artifact', 'id': value['id'],
            'artifact_type': value['artifact_type'], 'revision': int(value['revision']),
            'sha256': original.byte_sha256, 'hash_domain': 'legacy-original-bytes-v1',
            'legacy_manifest_sha256': legacy_hash}))
    return assemble_model_manifest(target['configuration'], binding, resources,
        scope_descriptor=descriptor, effective_profile=target['profile'].data)
