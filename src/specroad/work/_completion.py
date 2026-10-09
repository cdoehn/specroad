"""Inert, fully bound final result data; never execution or write authority."""

from ..model.canonical import canonical_json_bytes
from ._completion_outcome import _outcome, check_completed_controls
from ._data_contract import _copy, _count, _hash, _object, _parse, _require


def read_completion(value, objects, registry):
    """Check complete data and all supplied diagnostics, not execution truth."""
    from .manifest import _BINDING_FIELDS, _bytes
    _require(value['state'] == 'completed' and value['phase'] == 'completed'
             and value['frontier'] == []
             and value['next_action'] == {'operation': 'deliver_completed_work'})
    _require(type(value['result_parts']) is list and len(value['result_parts']) == 1
             and type(value['diagnostic_parts']) is list and len(value['diagnostic_parts']) == 1)
    raw = _bytes(value['result_parts'][0], objects)
    record = _parse(raw)
    _object(record, ('format_version', 'binding', 'completed_manifest_sha256',
                     'source_checkpoint_generation', 'source_checkpoint_sha256', 'outcome', 'exit_code'))
    _require(record['format_version'] == 'work-finalization-v1'
             and canonical_json_bytes(record) == raw)
    _require(canonical_json_bytes(record['binding'])
             == canonical_json_bytes({key: value[key] for key in _BINDING_FIELDS}))
    _hash(record['source_checkpoint_sha256']); _count(record['source_checkpoint_generation'])
    _require(record['source_checkpoint_generation'] >= 1
             and record['source_checkpoint_generation'] + 1 == value['checkpoint_generation']
             and record['completed_manifest_sha256'] == value['completed_manifest_sha256'])
    _outcome(value, record['outcome'], record['exit_code'], registry)
    diagnostics = canonical_json_bytes({'format_version': 'work-diagnostics-v1',
                                        'diagnostics': record['outcome']['diagnostics']})
    _require(_bytes(value['diagnostic_parts'][0], objects) == diagnostics)
    return record


def completion_candidate(manifest, outcome, exit_code):
    """Retain a trusted planner's complete result after every declared unit.

    Like partition_work_manifest, this factory only creates inert data. The
    planner remains responsible for declaring every mandatory global phase.
    Live adapters must separately check their closed plans and actual evidence.
    """
    from .manifest import WorkManifest, _BINDING_FIELDS, _put, _seal, read_work_successor
    _require(type(manifest) is WorkManifest)
    value = manifest.as_dict()
    _require(value['state'] == 'running' and not manifest.entries('remaining'))
    document = _copy(outcome)
    _outcome(value, document, exit_code, manifest._registry)
    record = {'format_version': 'work-finalization-v1',
        'binding': {key: value[key] for key in _BINDING_FIELDS},
        'completed_manifest_sha256': value['completed_manifest_sha256'],
        'source_checkpoint_generation': value['checkpoint_generation'],
        'source_checkpoint_sha256': value['checkpoint_sha256'],
        'outcome': document, 'exit_code': exit_code}
    objects = dict(manifest.objects)
    value['result_parts'] = [_put(canonical_json_bytes(record), objects)]
    value['diagnostic_parts'] = [_put(canonical_json_bytes({
        'format_version': 'work-diagnostics-v1', 'diagnostics': document['diagnostics']}), objects)]
    value['checkpoint_generation'] += 1
    value.update(state='completed', phase='completed', frontier=[],
                 next_action={'operation': 'deliver_completed_work'})
    return read_work_successor(_seal(value), objects, previous=manifest,
        registry=manifest._registry, expected_tool_build=value['tool_build'])
