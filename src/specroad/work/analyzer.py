"""Analyzer-owned inert requests on the existing durable Work journal.

The initial generation retains the analysis identity and all construction
inputs. A snapshot unit seals one complete native request; it never exposes a
partial successful request. Saved data cannot install an executor or writer.
"""
from pathlib import Path
from hashlib import sha256

from ..analyzers._values import encoded, require
from ..analyzers.requests import AnalyzerRequest
from ._analyzer_results import engines, check_engines, observation, pair_units, final_result
from ..model.canonical import canonical_json_bytes
from ._data_contract import _require, _parse
from .manifest import _bytes

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
            if control['format_version'] == 'analyzer-work-request-v2':
                from ..analyzers._work_values import check_engines as check_real_engines
                check_real_engines(request, evidence['engines'])
            else:
                check_engines(request,evidence['engines'])
        elif task['phase'] == 'subjects':
            _require(request is not None)
            subject = next(s for s in request.data['subjects'] if s['subject_key']==task['range']['subject_key'])
            if control['format_version'] == 'analyzer-work-request-v2':
                from ..analyzers._work_values import check_unit
                _require('snapshot' in done)
                check_unit(request, task['range'], done['snapshot']['engines'], evidence)
            else:
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


from ._analyzer_checkpoint import advance


def check_outcome(value, objects, document, exit_code):
    request = request_of(value, objects)
    _require(request is not None)
    control, _, done = checked_value(value, objects, None, validate_command=False)
    expected, code = completed_result(request, value['command_id'], control, done, document=document)
    _require(encoded(document) == expected.canonical_bytes and type(exit_code) is int and exit_code == code)


def completed_result(request, command_id, control, done, *, document=None):
    if command_id == 'analyzer.request':
        return request, 0
    if control['format_version'] == 'analyzer-work-request-v1':
        return final_result(request, command_id, done, document=document), 5
    from ..analyzers._work_values import package_from_units
    from ..analyzers.language_policy import execution_outcome
    result = package_from_units(request, done['snapshot']['engines'], done, document=document)
    return result, execution_outcome(result.reports, fail_on=control['fail_on'])['exit_code']


def outcome(manifest):
    from ._completion import read_completion
    value = manifest.as_dict()
    require(value['state'] == 'completed', 'analyzer_work_incomplete', exit_code=6)
    record = read_completion(value, manifest.objects, manifest._registry)
    return record['outcome'], record['exit_code']


def resume_analyzer_work(store, *, max_units=1, expected_analysis_id=None, expected_snapshot_sha256=None, executor=None):
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
    from contextlib import nullcontext
    from ..analyzers._work_worker import WorkWorker
    with (WorkWorker() if executor is None else nullcontext(executor)) as worker:
        for _ in range(max_units):
            if current.as_dict()['state'] == 'completed': break
            current = store._update(lambda previous: advance(previous, executor=worker))
    return current


__all__ = ('prepare_analyzer_work','checked','protected_paths','resume_analyzer_work','outcome','advance','engines')
