"""Native reference-source planner facade; no project writes or grants."""
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..storage.json_syntax import parse_json_object as parsed
from ..model.audit_values import Actor, UtcTimestamp
from ..model.errors import ModelError
from ..changes.core import prepare_change_plan
from ..changes.values import ChangePlan
from .reference01 import inventory_bytes
from .reference01.values import SCOPE
from .plan_values import (POLICY, STEP, SOURCE_CONTRACT, MANIFEST_PATH, MigrationPlanError,
    MigrationPlanning, require, owned_files, file_bindings, changes)
from .plan_contract import validate_inputs
from .plan_inputs import migration_inputs, target_contract, _target
from .plan_originals import _original_archive
from .relation_derivation import _relation, _SourceRelations
from .plan_target import _target_fields, _stamp, _manifest
from .requirement_mapping import authored_fields

PROJECT_SCOPE = {'scope_version': 'scope-v1', 'scope_kind': 'project', 'selector': {},
    'configuration_id': None, 'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'}
SPECIFICATION_SCOPE = {**PROJECT_SCOPE, 'scope_kind': 'specification'}


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
    # Invalid derivations cannot be hidden by missing target inputs.
    source_relations = _SourceRelations(inventory)
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
    archive, manifest, source_relations = _original_archive(inventory, source, report['target_contract'], source_relations)
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
        value['relations'] = source_relations.materialize(original)
        fields = ['id_scheme']
        if old['relations']: fields.extend(['relations/*/relation_id', 'relations/*/id_scheme'])
        if old['artifact_type'] == 'requirement':
            row = requirements[old['id']]
            value.update(authored_fields(row))
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
