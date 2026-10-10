"""Inert terminal cancellation control data, never a semantic result."""

from ..model.canonical import canonical_json_bytes
from ._data_contract import _count, _hash, _object, _parse, _require, _text


def read_cancellation(value, objects):
    from .manifest import _BINDING_FIELDS, _bytes
    _require(value['state'] == 'cancelled' and value['phase'] == 'cancelled'
             and value['frontier'] == [] and value['next_action'] is None)
    _require(type(value['result_parts']) is list and len(value['result_parts']) == 1
             and value['diagnostic_parts'] == [])
    raw = _bytes(value['result_parts'][0], objects)
    record = _parse(raw)
    _object(record, ('format_version', 'binding', 'source_checkpoint_generation',
        'source_checkpoint_sha256', 'completed_manifest_sha256',
        'remaining_manifest_sha256', 'reason'))
    _require(record['format_version'] == 'work-cancellation-v1'
             and canonical_json_bytes(record) == raw)
    _require(canonical_json_bytes(record['binding'])
             == canonical_json_bytes({key: value[key] for key in _BINDING_FIELDS}))
    _count(record['source_checkpoint_generation']); _hash(record['source_checkpoint_sha256'])
    _text(record['reason']); _require(bool(record['reason'].strip()))
    _require(record['source_checkpoint_generation'] + 1 == value['checkpoint_generation']
             and record['completed_manifest_sha256'] == value['completed_manifest_sha256']
             and record['remaining_manifest_sha256'] == value['remaining_manifest_sha256'])
    return record


def cancellation_candidate(manifest, reason):
    """Retain an unchanged partition and explicit reason in one new generation.

    A live adapter must separately prove cancellation is allowed. This pure
    factory neither inspects a project transaction nor authorizes cancellation.
    """
    from .manifest import WorkManifest, _BINDING_FIELDS, _put, _seal, read_work_successor
    _require(type(manifest) is WorkManifest)
    value = manifest.as_dict()
    _require(value['state'] == 'running')
    _text(reason); _require(bool(reason.strip()))
    record = {'format_version': 'work-cancellation-v1',
        'binding': {key: value[key] for key in _BINDING_FIELDS},
        'source_checkpoint_generation': value['checkpoint_generation'],
        'source_checkpoint_sha256': value['checkpoint_sha256'],
        'completed_manifest_sha256': value['completed_manifest_sha256'],
        'remaining_manifest_sha256': value['remaining_manifest_sha256'], 'reason': reason}
    objects = dict(manifest.objects)
    value['result_parts'] = [_put(canonical_json_bytes(record), objects)]
    value['checkpoint_generation'] += 1
    value.update(state='cancelled', phase='cancelled', frontier=[], next_action=None)
    return read_work_successor(_seal(value), objects, previous=manifest,
        registry=manifest._registry, expected_tool_build=value['tool_build'])
