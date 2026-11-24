"""Detached Force result contracts; no filesystem effects or authority."""
from ..model.canonical import canonical_json_sha256 as digest
from .write_guard_values import require


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
