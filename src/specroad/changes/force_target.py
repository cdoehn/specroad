"""Native validation findings over concrete bytes, independent of execution."""
from ..force import ForceDecisions
from ..model.canonical import canonical_json_sha256 as digest
from ..model.errors import ModelError
from ..bundles.errors import BundleError
from ..model.paths import project_path
from .write_guard_values import inventory, require


def effect_path(path):
    from ..bundles.migration_source import ADMIN_ROOTS
    project_path(path)
    require(path.split('/')[0] not in (*ADMIN_ROOTS, '.specroad'), 'force_target_not_product_resource', exit_code=2)


def gate_class(stage):
    return {'parsing': 'structure', 'schema_types_identity_fields': 'schema',
        'identities_references': 'references', 'graph': 'cycles', 'scope': 'references',
        'profiles': 'profiles', 'minimum_relations': 'references', 'stored_lifecycle_fields': 'lifecycle',
        'lifecycle': 'lifecycle', 'document_model': 'structure', 'review_currentness': 'review',
        'evidence_currentness': 'readiness', 'configuration': 'profiles', 'external_resources': 'readiness',
        'extension:task-readiness': 'task'}.get(stage, 'schema')


def assess_files(files, *, services=None, history=None):
    from ..qualification.project import project_validation_report
    root = None; diagnostics = []; native = None
    try:
        from ..model.configuration import ProjectConfiguration
        from ..model.paths import classify_path, PathClass
        from ..storage.json_syntax import parse_json_object
        if 'specroad.json' not in files:
            raise ModelError('force_project_configuration_missing', path='specroad.json')
        configuration = ProjectConfiguration(parse_json_object(files['specroad.json'], path='specroad.json'))
        # A configured registry is normative even when its declared path is
        # outside the generic managed directories. The native reader still
        # verifies its original bytes, version and digest; never synthesize it.
        registry_path = configuration.data.get('language_registry', {}).get('path')
        native_files = {path: raw for path, raw in files.items()
            if path == registry_path or classify_path(path, configuration) not in
                (PathClass.UNMANAGED, PathClass.GENERATED, PathClass.CACHE)}
        model, root, report = project_validation_report({**native_files, **(history or {})}, services=services)
        native = report.data
        diagnostics = [dict(d) for stage in native['stages'] for d in stage['diagnostics']]
        complete = native['checks_complete']
        status = 'invalid' if native['model_valid'] is False else 'valid' if complete and native['model_valid'] is True else 'unknown'
    except (ModelError, BundleError) as error:
        # The requested report is complete; the semantic examination is not.
        # No unparseable model receives an invented root or a passing stage.
        diagnostics = [{**(error.diagnostic() if hasattr(error, 'diagnostic') else {'reason': error.reason}), 'severity': 'error'}]
        status = 'unknown'; complete = False
    resources = []
    from ..storage.json_syntax import parse_json_object
    for path, raw in sorted(files.items()):
        row = {'path': path, 'parse_status': 'not_json', 'artifact_id': None, 'diagnostic': None}
        if path.endswith('.json'):
            try:
                value = parse_json_object(raw, path=path)
                row['parse_status'] = 'parsed'
                row['artifact_id'] = value.get('id') if type(value.get('id')) is str else None
            except ModelError as error:
                row['parse_status'] = 'unparseable'; row['diagnostic'] = error.diagnostic()
        resources.append(row)
    return {'format_version': 'force-target-report-v1', 'resources': resources, 'inventory': inventory(files),
        'inventory_sha256': digest(inventory(files)), 'model_root_sha256': root,
        'validation_status': status, 'checks_complete': complete, 'native': native,
        'diagnostics': diagnostics, 'approval_granted': False}


def record_findings(decisions, report, *, operation, requested_binding):
    decisions.observe_validation(report['validation_status'])
    native = report['native']
    if native is None:
        rows = [('structure:projection', None, report['diagnostics'])]
    else:
        rows = [(gate_class(stage['stage']) + ':' + stage['stage'],
                 False if stage['status'] == 'failed' else None, stage['diagnostics'])
                for stage in native['stages'] if stage['status'] not in ('passed', 'not_applicable')]
    for gate, allowed, diagnostics in rows:
        for diagnostic in diagnostics or [{'code': 'CORE_MODEL', 'reason': 'validation_unavailable'}]:
            if diagnostic.get('severity', 'error') == 'info' and allowed is False:
                continue
            decisions.decide(allowed, gate_id=gate, diagnostic_code=diagnostic.get('code') or 'CORE_MODEL',
                subject=diagnostic.get('artifact_id') or diagnostic.get('path') or 'project',
                operation=operation, observed_binding={'inventory_sha256': report['inventory_sha256'],
                    'model_root_sha256': report['model_root_sha256'], 'diagnostic': diagnostic},
                requested_binding=requested_binding, effect='execute_concrete_target_with_negative_finding')


def validate_report(value, target_inventory):
    from ._journal_codec import _hash
    fields = {'format_version', 'inventory', 'inventory_sha256', 'model_root_sha256',
        'validation_status', 'checks_complete', 'native', 'diagnostics', 'approval_granted', 'resources'}
    require(type(value) is dict and set(value) == fields and value['format_version'] == 'force-target-report-v1'
        and value['inventory'] == target_inventory and value['inventory_sha256'] == digest(target_inventory)
        and value['validation_status'] in ('valid', 'invalid', 'unknown')
        and type(value['checks_complete']) is bool and type(value['diagnostics']) is list
        and value['approval_granted'] is False and (value['model_root_sha256'] is None or _hash(value['model_root_sha256'])),
        'force_validation_binding')
    require(type(value['resources']) is list and [v.get('path') for v in value['resources'] if type(v) is dict]
        == [row['path'] for row in target_inventory], 'force_resource_report_binding')
    for row in value['resources']:
        require(type(row) is dict and set(row) == {'path', 'parse_status', 'artifact_id', 'diagnostic'}
            and row['parse_status'] in ('not_json', 'parsed', 'unparseable')
            and (row['artifact_id'] is None or type(row['artifact_id']) is str)
            and ((row['diagnostic'] is not None) == (row['parse_status'] == 'unparseable')), 'force_resource_report_fields')
    native = value['native']
    if native is None:
        require(value['validation_status'] == 'unknown' and not value['checks_complete']
            and value['model_root_sha256'] is None and bool(value['diagnostics']), 'force_unknown_not_passed')
    else:
        require(type(native) is dict and type(native.get('stages')) is list and bool(native['stages'])
            and type(native.get('checks_complete')) is bool and native.get('model_valid') in (True, False, None)
            and native.get('approval_granted') is False and native.get('write_authorized') is False, 'force_native_report_shape')
        for stage in native['stages']:
            require(type(stage) is dict and set(stage) == {'stage', 'status', 'checked_ids', 'diagnostics'}
                and type(stage['stage']) is str and stage['status'] in ('passed', 'failed', 'not_applicable', 'unavailable', 'blocked')
                and type(stage['checked_ids']) is list and type(stage['diagnostics']) is list, 'force_native_stage_shape')
        complete = all(v['status'] in ('passed', 'failed', 'not_applicable') for v in native['stages'])
        model_valid = False if any(v['status'] == 'failed' for v in native['stages']) else True if complete else None
        require(native['checks_complete'] == complete and native['model_valid'] is model_valid
            and value['model_root_sha256'] is not None, 'force_native_result_fold')
        expected = 'invalid' if native['model_valid'] is False else 'valid' if native['checks_complete'] and native['model_valid'] is True else 'unknown'
        require(value['validation_status'] == expected and value['checks_complete'] == native['checks_complete']
            and value['diagnostics'] == [dict(d) for s in native['stages'] for d in s['diagnostics']], 'force_native_report_binding')
