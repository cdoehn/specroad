"""Check retained native observations without rerunning their Fach evaluations.

These are consistency checks on data, not authentication of foreign work files.
The independently trusted initial binding and protected Work store still matter.
"""

from ..model.canonical import canonical_json_bytes
from ..validation import ModelDocument
from ..validation.diagnostics import assess_validation
from ..validation.values import ValidationReport, VALIDATION_VERSION, HOOK_NAMES
from ._data_contract import _object, _hash, _require


_REPORT_FIELDS = ('format_version', 'input_sha256', 'validation_scope', 'source_count',
    'structural_scope', 'source_bindings', 'identified_ids', 'identified_sources',
    'requested_ids', 'checked_ids', 'stages', 'checks_complete', 'model_valid',
    'approval_granted', 'write_authorized', 'project_files_verified', 'atomic_snapshot')
_STAGES = ('parsing', 'schema_types_identity_fields', 'identities_references', 'graph',
           'scope', 'profiles', 'minimum_relations', 'stored_lifecycle_fields', *sorted(HOOK_NAMES))


def _ids(value):
    _require(type(value) is list and all(type(v) is str and bool(v) for v in value)
             and len(value) == len(set(value)))
    return value


def check_validation_observation(current, task, observation):
    """Require every native phase and reconstruct its complete diagnostic view."""
    _require(type(observation) is dict and type(observation.get('source_report')) is dict)
    report = observation['source_report']; _object(report, _REPORT_FIELDS)
    _hash(report['input_sha256'])
    inputs = [row for row in current.entries('inputs') if row['root_id'] == 'model']
    bindings = [{k: row[k] for k in ('path', 'sha256')} for row in inputs]
    selected = task['range']['selected_ids']
    _require(report['format_version'] == VALIDATION_VERSION
        and report['structural_scope'] == 'all_supplied_documents'
        and report['source_bindings'] == bindings
        and type(report['source_count']) is int and report['source_count'] == len(inputs)
        and report['requested_ids'] == selected
        and report['validation_scope'] == ('loaded_model' if selected is None else 'dependency_expanded_loaded_scope')
        and report['checks_complete'] is True
        and all(report[k] is False for k in ('approval_granted', 'write_authorized',
                                             'project_files_verified', 'atomic_snapshot')))
    identified = _ids(report['identified_ids']); checked = _ids(report['checked_ids'])
    _require(identified == sorted(identified) and checked == sorted(checked)
        and set(checked) <= set(identified)
        and (checked == identified if selected is None else set(selected) <= set(checked)))
    sources = report['identified_sources']
    _require(type(sources) is list and len(sources) == len(inputs))
    for source in sources:
        _object(source, ('path', 'artifact_id'))
        _require(type(source['path']) is str and type(source['artifact_id']) is str)
    _require([s['path'] for s in sources] == [i['path'] for i in inputs]
             and sorted(s['artifact_id'] for s in sources) == identified)
    stages = report['stages']
    _require(type(stages) is list and len(stages) == len(_STAGES))
    for expected, stage in zip(_STAGES, stages):
        _object(stage, ('stage', 'status', 'checked_ids', 'diagnostics'))
        _require(stage['stage'] == expected and type(stage['diagnostics']) is list)
        ids = _ids(stage['checked_ids'])
        if expected == 'parsing' or expected in HOOK_NAMES:
            _require(ids == [] and stage['diagnostics'] == []
                and stage['status'] == ('passed' if expected == 'parsing' else 'not_applicable'))
        else:
            expected_ids = ([s['artifact_id'] for s in sources] if expected == 'schema_types_identity_fields'
                else identified if expected in ('identities_references', 'graph') else checked)
            _require(ids == expected_ids)
            if expected in ('profiles', 'minimum_relations'):
                _require(all(type(d) is dict for d in stage['diagnostics']))
                failed = any(d.get('severity', 'error') == 'error' for d in stage['diagnostics'])
                _require(stage['status'] == ('failed' if failed else 'passed'))
            else:
                _require(stage['status'] == 'passed' and stage['diagnostics'] == [])
    _require(report['model_valid'] is (not any(s['status'] == 'failed' for s in stages)))
    documents = tuple(ModelDocument(row['path'], current.objects[row['sha256']]) for row in inputs)
    # Only project already retained observations with the original Core adapter;
    # never run validate_model, graph evaluation, profile composition or a gate.
    projected = assess_validation(ValidationReport._create(report), documents=documents)
    _require(canonical_json_bytes(projected.as_dict()) == canonical_json_bytes(observation))
