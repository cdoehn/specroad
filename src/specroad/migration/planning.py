"""Native reference-source planning over owned bytes. No project writes or grants."""
from hashlib import sha256
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..storage.json_syntax import parse_json_object as parsed
from ..model.audit_values import Actor, UtcTimestamp
from ..model.configuration import ProjectConfiguration
from ..model.model_manifest import ProjectReadBinding, ManifestResource, assemble_model_manifest
from ..model.manifest_resources import project_json_resource
from ..model.identity_tokens import encode128
from ..model.errors import ModelError
from ..changes.metadata_time import next_update_time
from ..changes._common import _artifact
from ..changes.core import prepare_change_plan
from ..changes.values import ChangePlan
from ..profiles.values import ProfileResource
from ..profiles.composition import compose_profiles, check_composed_fields
from ..model.language_registry import LanguageRegistry
from ..model.language_package_values import LanguagePackage
from .reference01 import inventory_bytes
from .reference01.values import SCOPE, CONTRACT_ID, CONTRACT_VERSION, READER_ID
from .plan_values import (POLICY, STEP, SOURCE_CONTRACT, MANIFEST_PATH, MigrationPlanError,
    MigrationPlanning, require, owned_files, file_bindings, changes, safe_path, b64, unb64)
from .plan_contract import validate_inputs

PROJECT_SCOPE = {'scope_version': 'scope-v1', 'scope_kind': 'project', 'selector': {},
    'configuration_id': None, 'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'}
SPECIFICATION_SCOPE = {**PROJECT_SCOPE, 'scope_kind': 'specification'}


def migration_inputs(*, target_configuration=None, target_resources=None,
                     requirement_mappings=(), proposal_mappings=()):
    """Normalize explicitly supplied input order, never fill missing semantic data."""
    require(target_configuration is None or type(target_configuration) is bytes,
            'migration_configuration_bytes_required')
    resources = owned_files({} if target_resources is None else target_resources)
    sequences = []
    for rows in (requirement_mappings, proposal_mappings):
        require(type(rows) in (tuple, list) and all(type(r) is dict and
            type(r.get('artifact_id')) is str for r in rows), 'migration_mapping_required')
        sequences.append(sorted(rows, key=lambda r: r['artifact_id'].encode('utf-8')))
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


def _relation(project, identity, index, relation, seen):
    encoded = jcs(['specroad-relation-migration-0.1-to-0.2-v1', project, identity, index, relation])
    rid = 'REL-' + encode128(sha256(encoded).digest()[:16])
    require(rid not in seen or seen[rid] == encoded, 'migration_relation_id_collision')
    seen[rid] = encoded
    return {'relation_id': rid, 'id_scheme': 'derived128-v1', **relation}


def _original_archive(inventory, source, target_contract_value):
    """Keep source originals separate from every derived navigation value."""
    originals = inventory.originals; current_root = inventory.model_root_sha256
    by_snapshot = {(o.snapshot_root, o.path): o for o in originals}
    archive = dict(inventory.payloads); entries, seen, identities = [], {}, {}
    for original in originals:
        raw = original.source_bytes; address = 'archive/objects/' + original.byte_sha256[:2] + '/' + original.byte_sha256
        require(address not in source or source[address] == raw, 'migration_archive_collision', path=address)
        require(address not in archive or archive[address] == raw, 'migration_archive_collision', path=address)
        archive[address] = raw
        value = original.data if original.role != 'attachment' else {}
        artifact = original.role == 'artifact'
        if artifact:
            key = (value['id'], value['revision'])
            require(key not in identities or identities[key] == raw, 'migration_original_revision_conflict')
            identities[key] = raw
        relation_rows = []
        for index, relation in enumerate(value.get('relations', [])):
            projected = _relation(inventory.data['project_id'], value['id'], index, relation, seen)
            relation_rows.append({'index': index, 'relation_id': projected['relation_id'],
                'id_scheme': 'derived128-v1', 'original': relation})
        payloads = {}
        if value.get('artifact_type') == 'baseline':
            for row in value['manifest']:
                path = 'archive/objects/' + row['byte_sha256'][:2] + '/' + row['byte_sha256']
                payloads[path] = {'path': path, 'size': row['size'], 'sha256': row['byte_sha256']}
        for row in value.get('attachments', []):
            payloads[row['path']] = {k: row[k] for k in ('path', 'size', 'sha256')}
        if value.get('artifact_type') == 'code_ref':
            item = by_snapshot.get((original.snapshot_root, value['path']))
            require(item is not None, 'migration_original_payload_missing')
            payloads[value['path']] = {'path': value['path'], 'size': len(item.source_bytes), 'sha256': item.byte_sha256}
        if artifact:
            from .reference01.semantics import prose_payloads
            for path in prose_payloads(value, original.path):
                item = by_snapshot.get((original.snapshot_root, path))
                require(item is not None, 'migration_original_payload_missing')
                payloads[path] = {'path': path, 'size': len(item.source_bytes), 'sha256': item.byte_sha256}
        physical = [address]
        if (original.snapshot_root == current_root and original.classification != 'mutable'
                and source.get(original.path) == raw):
            physical.append(original.path)
        for path in sorted(set(physical)):
            entries.append({'path': path, 'logical_path': original.path, 'role': original.role,
                'artifact_id': value.get('id') if artifact else None,
                'artifact_type': value.get('artifact_type') if artifact else None,
                'source_schema_version': '0.1.0', 'original_size': len(raw),
                'original_byte_sha256': original.byte_sha256,
                'original_canonical_sha256': original.canonical_sha256,
                'source_model_root_sha256': original.snapshot_root,
                'original_revision': value.get('revision') if artifact else None,
                'legacy_reader_id': READER_ID,
                'identity_projection': {'id_scheme': 'legacy-sequential-v1'} if artifact else None,
                'relation_projections': relation_rows, 'referenced_payloads': [payloads[p] for p in sorted(payloads)],
                'migration_provenance': {'contract_id': CONTRACT_ID, 'contract_version': CONTRACT_VERSION,
                    'contract_sha256': SOURCE_CONTRACT['contract_sha256'], 'source_snapshot_root': original.snapshot_root}})
    unique = {}
    for row in entries:
        key = (row['path'], row['source_model_root_sha256'], row['logical_path'])
        require(key not in unique or unique[key] == row, 'migration_manifest_conflict')
        unique[key] = row
    manifest = {'schema_version': '0.2.0', 'mapping_id': 'legacy-preservation', 'mapping_version': '1.0.0',
        'legacy_manifest_version': '1.0.0',
        'source': {'project_id': inventory.data['project_id'], **SOURCE_CONTRACT,
                   'contract_id': CONTRACT_ID, 'contract_version': CONTRACT_VERSION},
        'target': {'project_id': inventory.data['project_id'], **target_contract_value},
        'entries': [unique[k] for k in sorted(unique)], 'proposal_transitions': []}
    return archive, manifest, seen


def _mapping_index(rows, originals, kind):
    index = {o.data['id']: o for o in originals if o.role == 'artifact'
             and o.classification == 'mutable' and o.data['artifact_type'] == kind}
    mappings = {}
    for row in rows:
        identity = row['artifact_id']
        require(identity in index, 'migration_mapping_subject_unknown')
        require(row['source_sha256'] == index[identity].canonical_sha256, 'migration_mapping_source_changed', exit_code=6)
        mappings[identity] = row
    missing = [{'reason': kind + '_mapping_required', 'path': index[key].path}
               for key in sorted(set(index) - set(mappings))]
    return mappings, missing


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


def _plan(files, *, inputs, actor, planned_at, change_plan_id, request_id, target_version):
    source = owned_files(files)
    inputs = parsed(jcs(inputs)); validate_inputs(inputs)
    require(target_version == '0.2.0', 'migration_target_version_mismatch')
    require(type(actor) is dict and set(actor) == {'actor_type', 'actor_id'}, 'migration_actor_required')
    actor = Actor(**actor).as_fields(); UtcTimestamp(planned_at)
    require(type(change_plan_id) is str and bool(change_plan_id.strip()), 'migration_plan_id_required')
    from ..changes.request_ids import normalize_request_id
    normalize_request_id(request_id)
    inventory = inventory_bytes(source); inv = inventory.data
    originals = tuple(o for o in inventory.originals if o.snapshot_root == inventory.model_root_sha256)
    config_source = parsed(source['specroad.json'])
    target, blockers = _target(inputs, inv['project_id'], config_source['id_prefix'])
    requirements, missing = _mapping_index(inputs['requirement_mappings'], originals, 'requirement'); blockers += missing
    proposals, missing = _mapping_index(inputs['proposal_mappings'], originals, 'proposal'); blockers += missing
    report = {'format_version': 'migration-planning-v1', 'source_contract': SOURCE_CONTRACT,
        'target_contract': target_contract(), 'source_model_root_sha256': inventory.model_root_sha256,
        'inputs_sha256': digest(inputs), 'ready': False, 'blockers': sorted(blockers, key=lambda x: (x['path'], x['reason'])),
        'change_plan': None, 'expected_target_model_root_sha256': None,
        'expected_proposal_basis_sha256': None, 'write_authorized': False, 'approval_granted': False,
        'public_apply_supported': False, 'backup_verified': False, 'current_readiness_verified': False}
    # Missing proposal plans do not prevent calculation of their required basis.
    if target is None or any(b['reason'] != 'proposal_mapping_required' for b in blockers):
        return MigrationPlanning._create(report)
    archive, manifest, relation_seen = _original_archive(inventory, source, report['target_contract'])
    current = dict(source); current.pop('profiles/core-reference01.json', None)
    current.update(target['files']); current['specroad.json'] = target['configuration_bytes']
    for path, raw in archive.items():
        require(path not in current or current[path] == raw, 'migration_archive_collision', path=path)
        current[path] = raw
    regular, legacy, pending, required_fields = [], [], [], []
    for original in originals:
        if original.role != 'artifact':
            continue
        old = original.data
        if original.classification == 'immutable_legacy':
            legacy.append(original); continue
        value = _stamp(old, actor, planned_at)
        value['relations'] = [_relation(inv['project_id'], old['id'], i, r, relation_seen)
                              for i, r in enumerate(old['relations'])]
        fields = ['id_scheme']
        if old['relations']: fields.extend(['relations/*/relation_id', 'relations/*/id_scheme'])
        if old['artifact_type'] == 'requirement':
            row = requirements[old['id']]
            value.update({k: row[k] for k in ('language', 'normative_force', 'statement')})
            fields += ['language', 'normative_force']
        if old['artifact_type'] == 'proposal':
            manifest['proposal_transitions'].append({'artifact_id': old['id'], 'source_revision': old['revision'],
                'source_sha256': original.canonical_sha256, 'target_revision': value['revision'],
                'target_content_revision': int(old['content_revision']) + 1})
            pending.append((original, value))
        else:
            _target_fields(value, target)
            regular.append(value); current[original.path] = jcs(value) + b'\n'
        required_fields.append({'path': original.path, 'fields': sorted(fields)})
    manifest['proposal_transitions'].sort(key=lambda r: r['artifact_id'])
    legacy_hash = digest(manifest)
    current[MANIFEST_PATH] = jcs(manifest) + b'\n'
    basis = _manifest(target, regular, legacy, legacy_hash, archive, inventory, SPECIFICATION_SCOPE)
    report['expected_proposal_basis_sha256'] = basis.sha256
    if blockers:
        return MigrationPlanning._create(report)
    for original, value in pending:
        mapped = ChangePlan(jcs(proposals[value['id']]['change_plan']))
        bound = mapped.data
        require(bound['metadata_policy_version'] == 'change-metadata-v1', 'migration_proposal_regular_plan_required')
        require(bound['base'] == {'scope_descriptor': SPECIFICATION_SCOPE, 'model_root_sha256': basis.sha256},
                'migration_proposal_target_basis_mismatch', exit_code=6)
        value.update(base=bound['base'], change_plan=bound, content_revision=int(original.data['content_revision']) + 1,
                     proposal_status='draft', maturity='draft')
        from ..proposals.values import content_sha256, ProposalOriginal
        value['content_sha256'] = content_sha256(value)
        _target_fields(value, target)
        ProposalOriginal(jcs(value), path=original.path)
        regular.append(value); current[original.path] = jcs(value) + b'\n'
    # Cross-resource collisions and file/directory conflicts are checked before any output.
    current = owned_files(current)
    final = _manifest(target, regular, legacy, legacy_hash, archive, inventory, PROJECT_SCOPE)
    results = [{'artifact': v, 'sha256': digest(v)} for v in sorted(regular, key=lambda v: v['id'])]
    source_rows, target_rows = file_bindings(source), file_bindings(current)
    protected = {o.path for o in originals if o.classification != 'mutable'
                 and source.get(o.path) == o.source_bytes} | set(dict(inventory.payloads))
    require(all(p in current and current[p] == source[p] for p in protected), 'migration_original_changed')
    operation = {'op': 'schema_migrate', 'format_version': 'schema-migrate-v1',
        'source_contract': SOURCE_CONTRACT, 'target_contract': report['target_contract'],
        'steps': [{'step_id': STEP, 'source_contract': SOURCE_CONTRACT, 'target_contract': report['target_contract'],
                   'direction': 'forward', 'reversible': False}],
        'inputs': inputs, 'inputs_sha256': digest(inputs), 'source_files': source_rows, 'target_files': target_rows,
        'changes': changes(source, current), 'result_ids': [r['artifact']['id'] for r in results],
        'source_model_root_sha256': inventory.model_root_sha256, 'target_model_root_sha256': final.sha256,
        'target_manifest': final.data, 'new_required_fields': sorted(required_fields, key=lambda r: r['path']),
        'losses': [], 'protected_paths': sorted(protected)}
    conditions = [{'kind': 'file', 'path': r['path'], 'expected_byte_sha256': r['sha256']} for r in source_rows]
    conditions += [{'kind': 'absent', 'path': r['path']} for r in target_rows if r['path'] not in source]
    plan = prepare_change_plan({'format_version': '1.2.0', 'metadata_policy_version': POLICY,
        'change_plan_id': change_plan_id, 'request_id': request_id, 'planned_at': planned_at, 'actor': actor,
        'base': {'scope_descriptor': SCOPE, 'model_root_sha256': inventory.model_root_sha256},
        'operations': [operation], 'preconditions': conditions, 'result_artifacts': results,
        'expected_result': {'model_root_sha256': final.sha256}})
    return MigrationPlanning._create({**report, 'ready': True, 'change_plan': plan.data,
                                     'expected_target_model_root_sha256': final.sha256})


def plan_migration(files, *, inputs, actor, planned_at, change_plan_id, request_id=None, target_version='0.2.0'):
    """Return a detached complete plan or explicit missing-input blockers. No I/O writes."""
    try:
        return _plan(files, inputs=inputs, actor=actor, planned_at=planned_at,
            change_plan_id=change_plan_id, request_id=request_id, target_version=target_version)
    except MigrationPlanError:
        raise
    except ModelError as error:
        raise MigrationPlanError(error.reason, path=error.path, pointer=error.pointer,
                                 exit_code=getattr(error, 'exit_code', 3)) from error
