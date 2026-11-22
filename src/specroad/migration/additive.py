"""Explicit 0.2 -> 0.3 project capability transition on the existing writer.

Only the caller-supplied configuration version changes. All other bytes,
including historical original formats and evidence, are protected inputs.
"""
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..storage.json_syntax import parse_json_object as parsed
from ..model.configuration import ProjectConfiguration
from ..changes.core import prepare_change_plan
from .plan_values import (POLICY, MigrationPlanning, require, owned_files, file_bindings, changes, unb64)
from .plan_contract import validate_inputs

STEP = 'project02-to-plan03.v1'
VERSION = '0.3.0'


def source_contract():
    from .plan_inputs import target_contract
    return target_contract()


def target_contract():
    from ..model.plan_schemas import plan_schema
    from ..model.configuration_schema import configuration_json_schema
    return {'schema_version': VERSION, 'contract_sha256': digest({
        'contract_version': 'additive-plan-project-v1', 'source_contract': source_contract(),
        'project': configuration_json_schema(VERSION),
        'implementation_plan': plan_schema('implementation_plan'), 'plan_entry': plan_schema('plan_entry')})}


def _observed(files):
    from ..qualification.project import project_bytes
    from .current_source import project_files
    model, root = project_bytes(project_files(files))
    return model, model.manifest(model.artifacts, {
        'scope_version': 'scope-v1', 'scope_kind': 'project', 'selector': {},
        'configuration_id': None, 'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'})


def plan(files, *, inputs, actor, planned_at, change_plan_id, request_id, target_version):
    from .reference01.values import SCOPE
    require(target_version == VERSION, 'migration_target_version_mismatch')
    source = owned_files(files, passive=True)
    inputs = parsed(jcs(inputs)); validate_inputs(inputs)
    original = ProjectConfiguration(parsed(source['specroad.json'])).data
    require(original['schema_version'] == '0.2.0', 'migration_source_version_mismatch')
    require(not inputs['target_resources'] and not inputs['requirement_mappings']
            and not inputs['proposal_mappings'], 'additive_migration_unexpected_mapping')
    model, before = _observed(source)
    report = {'format_version': 'migration-planning-v1', 'source_contract': source_contract(),
        'target_contract': target_contract(), 'source_model_root_sha256': before.sha256,
        'inputs_sha256': digest(inputs), 'ready': False, 'blockers': [], 'change_plan': None,
        'expected_target_model_root_sha256': None, 'expected_proposal_basis_sha256': None,
        'write_authorized': False, 'approval_granted': False, 'public_apply_supported': True,
        'backup_verified': False, 'current_readiness_verified': False, 'loss_report': None}
    if inputs['target_configuration'] is None:
        return MigrationPlanning._create({**report, 'blockers': [
            {'reason': 'target_configuration_required', 'path': 'specroad.json'}]})
    raw = unb64(inputs['target_configuration'])
    target = ProjectConfiguration(parsed(raw)).data
    require(target == {**original, 'schema_version': VERSION}, 'additive_migration_configuration_changed')
    current = {**source, 'specroad.json': raw}
    _, after = _observed(current)
    protected = sorted(set(source) - {'specroad.json'})
    rows = file_bindings(source)
    operation = {'op': 'schema_migrate', 'format_version': 'schema-migrate-v1',
        'source_contract': report['source_contract'], 'target_contract': report['target_contract'],
        'steps': [{'step_id': STEP, 'source_contract': report['source_contract'],
            'target_contract': report['target_contract'], 'direction': 'forward', 'reversible': False}],
        'inputs': inputs, 'inputs_sha256': digest(inputs), 'source_files': rows,
        'target_files': file_bindings(current), 'changes': changes(source, current), 'result_ids': [],
        'source_model_root_sha256': before.sha256, 'target_model_root_sha256': after.sha256,
        'target_manifest': after.data, 'new_required_fields': [], 'losses': [], 'protected_paths': protected}
    prepared = prepare_change_plan({'format_version': '1.2.0', 'metadata_policy_version': POLICY,
        'change_plan_id': change_plan_id, 'request_id': request_id, 'planned_at': planned_at, 'actor': actor,
        'base': {'scope_descriptor': SCOPE, 'model_root_sha256': before.sha256}, 'operations': [operation],
        'preconditions': [{'kind': 'file', 'path': r['path'], 'expected_byte_sha256': r['sha256']} for r in rows],
        'result_artifacts': [], 'expected_result': {'model_root_sha256': after.sha256}})
    # This is a byte-preservation report, never a measurement of existing evidence.
    loss = {'format_version': 'additive-migration-loss-v1', 'lossless': True, 'losses': [],
            'protected_files': file_bindings({p: source[p] for p in protected}),
            'changed_paths': ['specroad.json']}
    return MigrationPlanning._create({**report, 'ready': True, 'change_plan': prepared.data,
        'expected_target_model_root_sha256': after.sha256, 'loss_report': loss})


def validate_target(plan, source, target, *, gates=()):
    from .transaction_target import materialized_files
    from ..qualification.project import project_validation_report
    from ..validation import assess_validation
    require(not gates, 'additive_migration_native_gates_required')
    require(target == materialized_files(plan, source), 'migration_target_files_changed', exit_code=6)
    # Native specialist/history gates retain their required evidence. No callback
    # can replace these with a successful scalar or fabricate a human review.
    from .current_source import project_files
    model, root, report = project_validation_report(project_files(target))
    assessed = assess_validation(report,
        fail_on=model.configuration.data['validation_policy'].get('fail_on', 'error'), documents=model.documents)
    require(report.complete and assessed.passed, 'migration_target_validation_failed')
    require(root == plan.data['operations'][0]['target_model_root_sha256'], 'migration_target_root_mismatch')
    return report
