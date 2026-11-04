"""Native whole-target migration checks on the shared validation pipeline.

Originals remain source-typed. Host semantic gates are explicit trusted code;
neither a saved plan nor a project resource installs one.
"""
from ..changes.values import ChangePlan
from ..model.canonical import canonical_json_sha256 as digest
from ..profiles.values import ProfileResource
from ..model.language_package_values import LanguagePackage
from ..validation import ModelDocument, ModelGate, ValidationResources, validate_model, assess_validation
from .plan_values import require, unb64, file_bindings
from .plan_inputs import _target
from .legacy_manifest import validate_legacy_manifest
from .plan_recheck import recheck_migration_plan


def materialized_files(plan, source):
    target = dict(source)
    for change in plan.data['operations'][0]['changes']:
        if change['after_bytes_base64'] is None:
            target.pop(change['path'])
        else:
            target[change['path']] = unb64(change['after_bytes_base64'])
    return target


def validate_transaction_target(plan, source, target, *, gates=()):
    require(type(plan) is ChangePlan, 'migration_plan_required')
    op = plan.data['operations'][0]
    recheck_migration_plan(plan.source_bytes, source, expected_target_version='0.2.0',
        expected_inputs_sha256=op['inputs_sha256'], expected_plan_sha256=plan.sha256)
    require(file_bindings(target) == op['target_files'], 'migration_target_files_changed', exit_code=6)
    require(type(gates) in (tuple, list) and all(type(g) is ModelGate for g in gates),
            'migration_registered_gates_required')
    gates = tuple(gates)
    from ..storage.json_syntax import parse_json_object
    actual = parse_json_object(target['specroad.json'])
    legacy = validate_legacy_manifest(target, project_id=actual['project_id'])
    prefix = actual['id_prefix']
    config, missing = _target(op['inputs'], legacy.data['source']['project_id'], prefix)
    require(not missing, 'migration_target_resources_incomplete')
    profiles = [ProfileResource(raw) for path, raw in config['files'].items()
                if path.startswith('profiles/') and not path.startswith('profiles/language-data/')
                and path != config['configuration'].data.get('language_registry', {}).get('path')]
    packages = [LanguagePackage(raw) for path, raw in config['files'].items()
                if path.startswith('profiles/language-data/')
                and path != config['configuration'].data.get('language_registry', {}).get('path')]
    core = next(p for p in profiles if p.profile_id == 'core')
    resources = ValidationResources(target['specroad.json'], registry=config['registry'],
        profile_resources=profiles, core_key=core.key, language_packages=packages)
    documents = tuple(ModelDocument(path, raw) for path, raw in sorted(target.items())
        if path.startswith('spec/') and path.endswith('.json'))
    if not any(g.gate_id == 'document_model' for g in gates):
        def dependencies(context):
            return context.dependency_result({i: list(context.all_ids) for i in context.subjects})
        def document_model(context):
            from ..graph.references import RelationReferences
            from ..documents._structure_graph import _document_structure
            records = context.source_records
            values = {r.identity.id: r.data for r in records}
            if any(values[i]['artifact_type'] not in ('document', 'section') for i in context.subjects):
                return context.result([{'reason': 'migration_document_semantic_service_required', 'severity': 'error'}])
            _, _, _, issues = _document_structure(records, RelationReferences(records), values)
            return context.result(issues)
        gates += (ModelGate('document_model', 'migration-document-structure-v1', dependencies,
                            document_model, resources.sha256),)
    extra_resources = [p for p in config['files'] if p.startswith(('rules/', 'mappings/'))]
    require(not extra_resources or any(g.gate_id == 'extension:target-resources' for g in gates),
            'migration_target_resource_gate_required')
    report = validate_model(documents, profile=config['profile'], resources=resources,
                            gates=gates, legacy=legacy, document_role_scope='full_project')
    assessed = assess_validation(report,
        fail_on=resources.configuration.data['validation_policy'].get('fail_on', 'error'), documents=documents)
    require(report.complete and assessed.passed, 'migration_target_validation_failed')
    return report
