"""Analyzer-owned inert requests on the existing durable Work journal.

The initial generation retains the analysis identity and all construction
inputs. A snapshot unit seals one complete native request; it never exposes a
partial successful request. Saved data cannot install an executor or writer.
"""
from pathlib import Path
from hashlib import sha256

from ..analyzers._values import encoded, require
from ..analyzers.identities import AnalysisRequestId
from ..analyzers.requests import AnalyzerRequest
from ._analyzer_results import engines, check_engines, observation, pair_units, final_result
from ..analyzers.files import InputFile
from ..analyzers.subjects import request_from_project
from ..model.canonical import canonical_json_bytes
from ._data_contract import _require, _parse
from .manifest import (_partition, _tree, _put, _bytes,
    _task_binding, partition_work_manifest, complete_work_manifest)

COMMANDS = ('analyzer.request', 'analyzer.run')
CONTROL = 'construction.json'
SNAPSHOT = 'request.json'


from ._analyzer_request import command_binding, prepare_analyzer_work


def units(request, command_id):
    subjects = pair_units(request) if request is not None and command_id=='analyzer.run' else []
    return [dict(key='snapshot', phase='snapshot', range={'complete_request': True}),
            *subjects, dict(key='finalize', phase='finalize', range={'command_id':command_id})]


def _inputs(value, objects):
    from .manifest import _entries
    rows = _entries('inputs', value['manifests']['inputs'], objects)
    _require(all(row['root_id'] == 'analyzer' for row in rows))
    return {row['path']: _bytes({k:row[k] for k in ('sha256','size')}, objects) for row in rows}


def request_of(value, objects):
    raw = _inputs(value, objects).get(SNAPSHOT)
    return None if raw is None else AnalyzerRequest(raw)


def checked_value(value, objects, registry, *, validate_command=True):
    """Validate the closed analyzer plan and every retained completion."""
    from .manifest import _entries
    if validate_command:
        command_binding(registry, value['command_id'], value['normalized_arguments'])
    control = value['normalized_arguments']['construction']
    inputs = _inputs(value, objects)
    _require(inputs.get(CONTROL) == encoded(control))
    request = request_of(value, objects)
    _require(set(inputs) == ({CONTROL} if request is None else {CONTROL,SNAPSHOT}))
    if request is not None:
        _require(inputs[SNAPSHOT] == request.canonical_bytes
            and request.data['request_id'] == value['normalized_arguments']['analysis_id'])
    if request is not None:
        if control['request'] is not None:
            _require(request.canonical_bytes == AnalyzerRequest(encoded(control['request'])).canonical_bytes)
        else:
            data, supplied = request.data, control['supplied']
            _require(all(data[key] == supplied[key] for key in ('analyzers','settings','extensions'))
                and data['context']['resources'] == supplied['context'])
            groups = {}
            for subject in data['subjects']:
                groups.setdefault(subject['artifact_id'],set()).add(subject['field_pointer'])
            _require(all(fields == set(control['field_pointers']) for fields in groups.values()))
            if control['subject_ids'] is not None:
                _require(set(groups) == set(control['subject_ids']))
    expected_sources = dict(project_id=None, scope=[],
        model_root_sha256=None)
    _require(value['source_bindings'] == expected_sources)
    tasks = _entries('tasks', value['manifests']['tasks'], objects)
    _require([{k:t[k] for k in ('key','phase','range')} for t in tasks] == units(request, value['command_id']))
    completed = _entries('completed', value['manifests']['completed'], objects)
    task_by_id = {t['unit_id']: t for t in tasks}
    done = {}
    for item in completed:
        task = task_by_id[item['unit_id']]
        raw = _bytes(item['evidence'], objects)
        evidence = _parse(raw)
        _require(raw == canonical_json_bytes(evidence))
        if task['key'] == 'snapshot':
            from ._data_contract import _object
            _object(evidence, ('request_sha256','engines'))
            _require(request is not None and evidence['request_sha256']==sha256(request.canonical_bytes).hexdigest())
            check_engines(request,evidence['engines'])
        elif task['phase'] == 'subjects':
            _require(request is not None)
            subject = next(s for s in request.data['subjects'] if s['subject_key']==task['range']['subject_key'])
            _require(evidence == observation(subject))
        elif task['key'] == 'finalize':
            _require(request is not None and evidence == {'prepared':True})
        done[task['key']] = evidence
    _require(list(done) == [task['key'] for task in tasks[:len(done)]])
    _require(('snapshot' in done) == (request is not None))
    return control, request, done


def checked(manifest):
    return checked_value(manifest.as_dict(), manifest.objects, manifest._registry)


def snapshot_successor(previous, current):
    """Only the single snapshot sealing transition may extend the bindings."""
    before, after = previous.as_dict(), current.as_dict()
    _require(request_of(before, previous.objects) is None
        and request_of(after, current.objects) is not None
        and before['state'] == after['state'] == 'running')
    _require(not previous.entries('completed') and len(current.entries('completed')) == 1)
    _require(_inputs(before, previous.objects)[CONTROL] == _inputs(after, current.objects)[CONTROL])
    _require(before['normalized_arguments'] == after['normalized_arguments'])


def protected_paths(initial):
    control, _, _ = checked(initial)
    paths = [Path(control['project'])] if control['project'] is not None else []
    paths += [Path(item['path']) for item in control['guards']]
    if control['output'] is not None:
        from ..analyzers.files import output_target
        boundary, path, current = output_target(control['output'],
            root=None if control['project'] is None else Path(control['project']),
            output_root=control['output_root'], cwd=control['cwd'])
        current()
        paths.append(boundary.root/path)
    return tuple(dict.fromkeys(paths))


def _guards(control):
    if control['project'] is not None:
        root = Path(control['project'])
        require(root.resolve(strict=True) == root, 'analyzer_work_project_changed', exit_code=6)
        info = root.stat()
        require([info.st_dev,info.st_ino] == control['project_identity'], 'analyzer_work_project_changed', exit_code=6)
    for item in control['guards']:
        current = InputFile(item['path'], control['cwd'])
        require(current.raw.hex() == item['raw_hex'], 'analyzer_work_input_changed', exit_code=6)
        current.current()


def _capture(control, identity):
    _guards(control)
    request = (AnalyzerRequest(encoded(control['request'])) if control['request'] is not None else
        request_from_project(Path(control['project']), **control['supplied'],
            subject_ids=control['subject_ids'], field_pointers=control['field_pointers'],
            configuration_id=control['configuration_id'], analysis_id=AnalysisRequestId(identity)))
    _guards(control)
    return request


def advance(manifest):
    """One complete native unit; no output publication or journal mutation."""
    control, request, done = checked(manifest)
    value = manifest.as_dict()
    require(value['state'] in ('running','completed'), 'analyzer_work_not_running', exit_code=6)
    if value['state'] == 'completed': return manifest
    if request is None:
        request = _capture(control, value['normalized_arguments']['analysis_id'])
        objects = dict(manifest.objects)
        rows = manifest.entries('inputs')
        rows.append(dict(root_id='analyzer', path=SNAPSHOT, **_put(request.canonical_bytes,objects)))
        value['manifests']['inputs'] = _tree('inputs', sorted(rows,key=lambda r:(r['root_id'],r['path'])), objects)
        command = {k:value[k] for k in ('command_id','command_class','normalized_arguments')}
        binding = _task_binding(command, value['source_bindings'], '', {})
        tasks = [dict(unit, unit_id='UNIT-'+sha256(encoded({'binding':binding,'unit':unit})).hexdigest())
                 for unit in units(request, value['command_id'])]
        value['manifests']['tasks'] = _tree('tasks', tasks, objects)
        complete = [{'unit_id':tasks[0]['unit_id'], 'evidence':_put(encoded({'request_sha256':sha256(request.canonical_bytes).hexdigest(),'engines':engines(request)}),objects)}]
        value['checkpoint_generation'] += 1
        return _partition(value,tasks,complete,objects,manifest._registry,value['tool_build'])
    require(engines(request)==done['snapshot']['engines'], 'analyzer_work_engine_changed', exit_code=6)
    if manifest.entries('remaining'):
        task = manifest.entries('remaining')[0]
        evidence = {'prepared':True}
        if task['phase']=='subjects':
            from ._analyzer_results import prepare_subject
            evidence = prepare_subject(request,task)
        return partition_work_manifest(manifest, {task['unit_id']: encoded(evidence)})
    result = final_result(request, value['command_id'], done)
    return complete_work_manifest(manifest, result.data, exit_code=0 if value['command_id']=='analyzer.request' else 5)


def check_outcome(value, objects, document, exit_code):
    request = request_of(value, objects)
    _require(request is not None)
    _, _, done = checked_value(value, objects, None, validate_command=False)
    expected = final_result(request, value['command_id'], done, document=document)
    _require(encoded(document) == expected.canonical_bytes
        and type(exit_code) is int and exit_code == (0 if value['command_id']=='analyzer.request' else 5))


def outcome(manifest):
    from ._completion import read_completion
    value = manifest.as_dict()
    require(value['state'] == 'completed', 'analyzer_work_incomplete', exit_code=6)
    record = read_completion(value, manifest.objects, manifest._registry)
    return record['outcome'], record['exit_code']


def resume_analyzer_work(store, *, max_units=1, expected_analysis_id=None, expected_snapshot_sha256=None):
    from .control import _initial
    from .resume import _runtime_build
    require(type(max_units) is int and max_units > 0, 'analyzer_work_unit_count', exit_code=2)
    _initial(store, _runtime_build())
    current = store.read()
    require(current is not None, 'analyzer_work_checkpoint_missing', exit_code=5)
    _, bound_request, _ = checked(current)
    if expected_analysis_id is not None:
        require(expected_analysis_id == current.as_dict()['normalized_arguments']['analysis_id'],
            'analyzer_work_identity_changed', exit_code=6)
    if expected_snapshot_sha256 is not None:
        require(bound_request is not None and expected_snapshot_sha256 == bound_request.data['snapshot_sha256'],
            'analyzer_work_snapshot_changed', exit_code=6)
    for _ in range(max_units):
        if current.as_dict()['state'] == 'completed': break
        current = store._update(advance)
    return current


__all__ = ('prepare_analyzer_work','checked','protected_paths','resume_analyzer_work','outcome','advance')
