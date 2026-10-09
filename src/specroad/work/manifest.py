"""Closed, inert work-v1 candidates with complete declared manifest partitions.

These values are not durable checkpoints or execution approvals. The codec
binds read-only structured requests or original normative ChangePlan bytes and
authoring identity. A trusted planner supplies the full unit plan; this module
proves its structural retention, not complete command coverage or authorization.
"""

from dataclasses import dataclass
from collections.abc import Mapping
from hashlib import sha256
from types import MappingProxyType
import secrets

from ..cli.contracts import CommandUsageError
from ..cli.requests import CommandRequest
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.identity_tokens import encode128, decode128
from ._data_contract import (
    WorkManifestError, _require, _object, _text, _hash, _count, _path, _copy, _parse,
)
from ._request_binding import _command, _tool, _sources
from ._phase import phase_name as _phase_name, frontier as _phase_frontier
from ._phase import next_action as _next_action, progress as _progress


_KINDS = ('inputs', 'tasks', 'completed', 'remaining')
_FANOUT = 64
_VERSIONS = {'work_manifest': 'work-manifest-segments-v1'}
_BINDING_FIELDS = (
    'work_format_version', 'work_id', 'command_id', 'command_class',
    'normalized_arguments', 'actor', 'request_id', 'operations_sha256',
    'tool_build', 'algorithm_versions', 'schema_versions', 'source_bindings',
    'input_manifest_sha256', 'task_manifest_sha256', 'plan_binding',
)
_FIELDS = {
    'work_format_version', 'work_id', 'checkpoint_generation', 'command_id',
    'command_class', 'normalized_arguments', 'actor', 'request_id', 'operations_sha256',
    'tool_build', 'algorithm_versions', 'schema_versions', 'source_bindings',
    'input_manifest_sha256', 'task_manifest_sha256', 'completed_manifest_sha256',
    'remaining_manifest_sha256', 'manifests', 'plan_binding', 'phase', 'frontier',
    'cursors', 'result_parts', 'diagnostic_parts', 'progress', 'consumption',
    'state', 'blocked_reason', 'next_action', 'checkpoint_sha256',
}


def _put(raw, objects):
    _require(type(raw) is bytes)
    digest = sha256(raw).hexdigest()
    objects[digest] = raw
    return {'sha256': digest, 'size': len(raw)}


def _bytes(reference, objects):
    _object(reference, ('sha256', 'size'))
    _hash(reference['sha256']); _count(reference['size'])
    raw = objects.get(reference['sha256'])
    _require(type(raw) is bytes and len(raw) == reference['size']
             and sha256(raw).hexdigest() == reference['sha256'])
    return raw


def _segment(kind, records, objects, *, branch=False):
    count = sum(item['count'] for item in records) if branch else len(records)
    value = {'format_version': 'work-manifest-segment-v1', 'kind': kind,
             'children' if branch else 'entries': records}
    reference = _put(canonical_json_bytes(value), objects)
    return {'id': 'SEG-' + reference['sha256'], **reference, 'count': count}


def _tree(kind, records, objects):
    level = [_segment(kind, records[i:i + _FANOUT], objects)
             for i in range(0, len(records), _FANOUT)]
    if not level:
        level = [_segment(kind, [], objects)]
    while len(level) > 1:
        level = [(_segment(kind, level[i:i + _FANOUT], objects, branch=True)
                  if len(level[i:i + _FANOUT]) > 1 else level[i])
                 for i in range(0, len(level), _FANOUT)]
    return level[0]


def _entries(kind, reference, objects):
    pending = [reference]
    result = []
    seen = set()
    while pending:
        current = pending.pop()
        _object(current, ('id', 'sha256', 'size', 'count'))
        _hash(current['sha256'])
        _require(current['sha256'] not in seen)
        seen.add(current['sha256'])
        _count(current['count'])
        _require(current['id'] == 'SEG-' + current['sha256'])
        value = _parse(_bytes({k: current[k] for k in ('sha256', 'size')}, objects))
        branch = 'children' in value
        field = 'children' if branch else 'entries'
        _object(value, ('format_version', 'kind', field))
        _require(value['format_version'] == 'work-manifest-segment-v1' and value['kind'] == kind)
        items = value[field]
        _require(type(items) is list and len(items) <= _FANOUT)
        if branch:
            _require(len(items) > 1)
            for child in items:
                _object(child, ('id', 'sha256', 'size', 'count'))
                _count(child['count'])
                _require(child['count'] > 0)
            _require(sum(child['count'] for child in items) == current['count'])
            pending.extend(reversed(items))
        else:
            _require(len(items) == current['count'])
            result.extend(items)
    _require(len(result) == reference['count'])
    return result


def _seal(value):
    value = dict(value)
    value.pop('checkpoint_sha256', None)
    value['checkpoint_sha256'] = sha256(canonical_json_bytes(value)).hexdigest()
    return canonical_json_bytes(value)


@dataclass(frozen=True, init=False)
class _WorkObjects(Mapping):
    """Immutable native-byte store; arbitrary mapping proxies are not trusted."""

    _data: object

    def __init__(self, *args, **kwargs):
        raise WorkManifestError('Use the checked work manifest factories')

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)


def _objects(value):
    _require(type(value) is dict or type(value) is _WorkObjects)
    if type(value) is _WorkObjects:
        return value
    # Reject foreign keys before any keyed lookup can invoke their hooks.
    for key, raw in value.items():
        _hash(key)
        _require(type(raw) is bytes and sha256(raw).hexdigest() == key)
    instance = object.__new__(_WorkObjects)
    object.__setattr__(instance, '_data', MappingProxyType(dict(value)))
    return instance


@dataclass(frozen=True, init=False)
class WorkManifest:
    """A checked data candidate; not a trusted CLI continuation approval."""

    raw: bytes
    objects: object
    _registry: object

    def __init__(self, *args, **kwargs):
        raise WorkManifestError('Use the checked work manifest factories')

    def as_dict(self):
        return _parse(self.raw)

    def entries(self, kind):
        _require(type(kind) is str and kind in _KINDS)
        return _entries(kind, self.as_dict()['manifests'][kind], self.objects)


def create_work_manifest(registry, request, *, tool_build, source_bindings, inputs, units):
    """Bind a trusted planner's complete finite declaration without running it.

    Each input has root_id/path/raw. Each unit has key/phase/range, where range
    is a JSON object describing the deterministic portion chosen by the planner.
    Work identity uses fresh operating-system entropy once, before any partition.
    """
    command = _command(registry, request)
    return _create_manifest(registry, command, tool_build=tool_build,
        source_bindings=source_bindings, inputs=inputs, units=units)


def create_normative_work_manifest(registry, request, *, plan, tool_build,
                                   source_bindings, inputs, units):
    """Bind an original ChangePlan for later fresh checks, never authorizing writes.

    The trusted host supplies its actual registered change.apply contract. This
    does not install a placeholder command in the built-in CLI registry.
    """
    from ._normative_binding import plan_values
    command = _command(registry, request, normative=True)
    metadata, objects = plan_values(plan)
    return _create_manifest(registry, command, tool_build=tool_build,
        source_bindings=source_bindings, inputs=inputs, units=units,
        authoring=metadata, extra_objects=objects)


def _task_binding(command, source_bindings, input_hash, authoring):
    value = {**command, 'source_bindings': source_bindings, 'input_manifest_sha256': input_hash}
    if command['command_class'] == 'normative_write':
        value.update(authoring)
    return sha256(canonical_json_bytes(value)).hexdigest()


def _create_manifest(registry, command, *, tool_build, source_bindings, inputs, units,
                     authoring=None, extra_objects=None):
    _tool(tool_build); _sources(source_bindings)
    _require(type(inputs) is list and type(units) is list and bool(units))
    if authoring is None:
        authoring = {'actor': None, 'request_id': None, 'operations_sha256': None, 'plan_binding': None}
    objects, input_rows = dict(extra_objects or {}), []
    for item in inputs:
        _object(item, ('root_id', 'path', 'raw'))
        _text(item['root_id']); _path(item['path'])
        input_rows.append({'root_id': item['root_id'], 'path': item['path'],
                           **_put(item['raw'], objects)})
    input_rows.sort(key=lambda item: (item['root_id'], item['path']))
    input_ref = _tree('inputs', input_rows, objects)
    binding = _task_binding(command, source_bindings, input_ref['sha256'], authoring)
    tasks = []
    for unit in units:
        _object(unit, ('key', 'phase', 'range'))
        _text(unit['key']); _text(unit['phase'])
        _require(type(unit['range']) is dict)
        declaration = _copy(unit)
        identity = sha256(canonical_json_bytes({'binding': binding, 'unit': declaration})).hexdigest()
        tasks.append({**declaration, 'unit_id': 'UNIT-' + identity})
    value = {
        'work_format_version': '1.0.0', 'work_id': 'WORK-' + encode128(secrets.token_bytes(16)),
        'checkpoint_generation': 0, **command,
        **authoring,
        'tool_build': _copy(tool_build), 'algorithm_versions': dict(_VERSIONS),
        'schema_versions': {'work': '1.0.0'}, 'source_bindings': _copy(source_bindings),
        'manifests': {'inputs': input_ref, 'tasks': _tree('tasks', tasks, objects)},
        'cursors': {}, 'result_parts': [], 'diagnostic_parts': [],
        'consumption': {'invocation': None, 'cumulative': None, 'measurement_status': 'unrecorded'},
        'state': 'running', 'blocked_reason': None,
    }
    return _partition(value, tasks, [], objects, registry, tool_build)


def _partition(value, tasks, completed, objects, registry, tool_build):
    done = {item['unit_id'] for item in completed}
    remaining = [task for task in tasks if task['unit_id'] not in done]
    value = _copy(value)
    value['manifests'].update(completed=_tree('completed', completed, objects),
                              remaining=_tree('remaining', remaining, objects))
    for kind, field in (('inputs', 'input'), ('tasks', 'task'),
                        ('completed', 'completed'), ('remaining', 'remaining')):
        value[field + '_manifest_sha256'] = value['manifests'][kind]['sha256']
    value['phase'] = _phase_name(remaining)
    value['frontier'] = _phase_frontier(remaining)
    value['progress'] = _progress(len(completed), len(tasks))
    value['next_action'] = _next_action(remaining)
    return read_work_manifest(_seal(value), objects, registry=registry, expected_tool_build=tool_build)


def partition_work_manifest(manifest, completions):
    """Record additional declared completion evidence in a new data candidate.

    Completion evidence must be inert JSON object bytes, one per known unit ID.
    This proves data retention and partition membership, not execution truth.
    Earlier object bytes remain available; no files are written or removed.
    """
    _require(type(manifest) is WorkManifest and type(completions) is dict and bool(completions))
    _require(all(type(key) is str for key in completions))
    value = manifest.as_dict()
    _require(value['state'] == 'running')
    tasks, completed = manifest.entries('tasks'), manifest.entries('completed')
    valid = {item['unit_id'] for item in tasks}
    done = {item['unit_id'] for item in completed}
    _require(set(completions) <= valid and not set(completions) & done)
    objects = dict(manifest.objects)
    for identity, raw in completions.items():
        _parse(raw)
        completed.append({'unit_id': identity, 'evidence': _put(raw, objects)})
    order = {task['unit_id']: index for index, task in enumerate(tasks)}
    completed.sort(key=lambda item: order[item['unit_id']])
    value['checkpoint_generation'] += 1
    return _partition(value, tasks, completed, objects, manifest._registry, value['tool_build'])


def complete_work_manifest(manifest, outcome, *, exit_code):
    """Create inert completed data after every declared unit, not an approval."""
    from ._completion import completion_candidate
    return completion_candidate(manifest, outcome, exit_code)


def read_work_manifest(raw, objects, *, registry, expected_tool_build):
    """Validate inert data; use read_work_successor for an expected prior work.

    This standalone reader does not authenticate the supplied work identity.
    Objects must be a native dict or the immutable store from this codec.
    """
    value = _parse(raw)
    _object(value, _FIELDS)
    _require(value['work_format_version'] == '1.0.0')
    _text(value['work_id']); _require(value['work_id'].startswith('WORK-'))
    try:
        decode128(value['work_id'][5:])
    except ModelError as error:
        raise WorkManifestError('Invalid work identity') from error
    _count(value['checkpoint_generation'])
    objects = _objects(objects)
    _tool(expected_tool_build); _tool(value['tool_build'])
    _require(value['tool_build'] == expected_tool_build)
    _require(value['algorithm_versions'] == _VERSIONS and value['schema_versions'] == {'work': '1.0.0'})
    _object(value['normalized_arguments'], ('options', 'arguments'))
    try:
        request = CommandRequest(value['command_id'], **value['normalized_arguments'])
    except CommandUsageError as error:
        raise WorkManifestError('Invalid structured work request') from error
    command = _command(registry, request, normative=value['command_class'] == 'normative_write')
    _require(all(value[name] == item for name, item in command.items()))
    _require(value['blocked_reason'] is None)
    _sources(value['source_bindings'])
    authoring = {name: value[name] for name in ('actor', 'request_id', 'operations_sha256', 'plan_binding')}
    if command['command_class'] == 'normative_write':
        from ._normative_binding import read_plan
        read_plan(value, objects)
    else:
        _require(all(item is None for item in authoring.values()))
    _object(value['manifests'], _KINDS)
    rows = {kind: _entries(kind, value['manifests'][kind], objects) for kind in _KINDS}
    for kind, field in (('inputs', 'input'), ('tasks', 'task'),
                        ('completed', 'completed'), ('remaining', 'remaining')):
        _require(value[field + '_manifest_sha256'] == value['manifests'][kind]['sha256'])
    seen = set()
    for item in rows['inputs']:
        _object(item, ('root_id', 'path', 'size', 'sha256'))
        _text(item['root_id']); _path(item['path'])
        key = (item['root_id'], item['path'])
        _require(key not in seen); seen.add(key)
        _bytes({k: item[k] for k in ('size', 'sha256')}, objects)
    _require(rows['inputs'] == sorted(rows['inputs'], key=lambda item: (item['root_id'], item['path'])))
    binding = _task_binding(command, value['source_bindings'], value['input_manifest_sha256'], authoring)
    tasks, keys = {}, set()
    for task in rows['tasks']:
        _object(task, ('key', 'phase', 'range', 'unit_id'))
        _text(task['key']); _text(task['phase']); _require(type(task['range']) is dict)
        declaration = {k: task[k] for k in ('key', 'phase', 'range')}
        identity = 'UNIT-' + sha256(canonical_json_bytes({'binding': binding, 'unit': declaration})).hexdigest()
        _require(task['unit_id'] == identity and identity not in tasks and task['key'] not in keys)
        tasks[identity] = task; keys.add(task['key'])
    _require(bool(tasks))
    completed = set()
    for item in rows['completed']:
        _object(item, ('unit_id', 'evidence'))
        _text(item['unit_id'])
        _require(item['unit_id'] in tasks and item['unit_id'] not in completed)
        completed.add(item['unit_id'])
        _parse(_bytes(item['evidence'], objects))
    remaining = [task for identity, task in tasks.items() if identity not in completed]
    _require(canonical_json_bytes(rows['remaining']) == canonical_json_bytes(remaining))
    _require([item['unit_id'] for item in rows['completed']]
             == [identity for identity in tasks if identity in completed])
    _require(value['progress'] == _progress(len(completed), len(tasks)))
    _require(type(value['progress']['completed_units']) is int and type(value['progress']['total_units']) is int)
    _require(value['cursors'] == {})
    _require(value['consumption'] == {'invocation': None, 'cumulative': None, 'measurement_status': 'unrecorded'})
    if value['state'] == 'completed':
        from ._completion import read_completion
        _require(not remaining)
        read_completion(value, objects, registry)
    else:
        _require(value['state'] == 'running'
                 and value['result_parts'] == [] and value['diagnostic_parts'] == [])
        _require(value['phase'] == (_phase_name(remaining)))
        _require(value['frontier'] == (_phase_frontier(remaining)))
        _require(value['next_action'] == _next_action(remaining))
    _hash(value['checkpoint_sha256'])
    sealed = _parse(_seal(value))
    _require(sealed['checkpoint_sha256'] == value['checkpoint_sha256'])
    instance = object.__new__(WorkManifest)
    object.__setattr__(instance, 'raw', canonical_json_bytes(value))
    object.__setattr__(instance, 'objects', objects)
    object.__setattr__(instance, '_registry', registry)
    return instance


def read_work_successor(raw, objects, *, previous, registry, expected_tool_build):
    """Check an immediate data successor against a caller-trusted prior value.

    The caller must obtain previous from its trusted work binding, not from the
    same untrusted package. No handler, filesystem or continuation approval is
    involved. Actual execution evidence and durable publication remain separate.
    """
    _require(type(previous) is WorkManifest)
    current = read_work_manifest(raw, objects, registry=registry,
                                 expected_tool_build=expected_tool_build)
    before, after = previous.as_dict(), current.as_dict()
    _require(all(canonical_json_bytes(before[name]) == canonical_json_bytes(after[name])
                 for name in _BINDING_FIELDS))
    _require(after['checkpoint_generation'] == before['checkpoint_generation'] + 1)
    old_done = {item['unit_id']: item for item in previous.entries('completed')}
    new_done = {item['unit_id']: item for item in current.entries('completed')}
    _require(before['state'] == 'running')
    if after['state'] == 'completed':
        from ._completion import read_completion
        record = read_completion(after, current.objects, registry)
        _require(not previous.entries('remaining') and new_done == old_done
                 and record['source_checkpoint_generation'] == before['checkpoint_generation']
                 and record['source_checkpoint_sha256'] == before['checkpoint_sha256'])
    else:
        _require(len(new_done) > len(old_done) and old_done.keys() <= new_done.keys())
    _require(all(new_done[key] == item for key, item in old_done.items()))
    _require(all(current.objects.get(key) == raw for key, raw in previous.objects.items()))
    return current
