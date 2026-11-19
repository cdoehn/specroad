"""Analyzer-owned inert requests on the existing durable Work journal.

The initial generation retains the analysis identity and all construction
inputs. A snapshot unit seals one complete native request; it never exposes a
partial successful request. Saved data cannot install an executor or writer.
"""
from pathlib import Path
import os
from hashlib import sha256

from ..analyzers._values import encoded, decode, require
from ..analyzers.identities import prepare_analysis_id, AnalysisRequestId
from ..analyzers.requests import AnalyzerRequest
from ..analyzers.file_adapter import default_inputs, request_inputs, unavailable_package
from ..analyzers.files import InputFile
from ..analyzers.subjects import request_from_project
from ..cli.contracts import CommandClass, EffectScope
from ..model.canonical import canonical_json_bytes
from ._data_contract import _require, _object, _parse, WorkManifestError
from .manifest import (_create_manifest, _partition, _tree, _put, _bytes,
    _task_binding, partition_work_manifest, complete_work_manifest)
from .resume import _runtime_build

COMMANDS = ('analyzer.request', 'analyzer.run')
CONTROL = 'construction.json'
SNAPSHOT = 'request.json'


def command_binding(registry, command_id, arguments):
    _require(command_id in COMMANDS)
    _object(arguments, ('analysis_id', 'construction'))
    AnalysisRequestId(arguments['analysis_id'])
    control = arguments['construction']
    _object(control, ('format_version','project','supplied','subject_ids','field_pointers',
        'configuration_id','request','guards','output','output_root','cwd','project_identity'))
    _require(control['format_version'] == 'analyzer-work-request-v1')
    _require(type(control['guards']) is list)
    for guard in control['guards']:
        _object(guard, ('path','document','raw_hex'))
        _require(type(guard['raw_hex']) is str)
        try:
            original = bytes.fromhex(guard['raw_hex'])
        except ValueError as error:
            raise WorkManifestError('Invalid captured input bytes') from error
        _require(original.hex() == guard['raw_hex'] and decode(original) == guard['document'])
        _require(type(guard['document']) is dict)
        _absolute(guard['path'])
    for key in ('project','output_root'):
        if control[key] is not None: _absolute(control[key])
    _absolute(control['cwd'])
    identity = control['project_identity']
    if control['project'] is None:
        _require(identity is None)
    else:
        _require(type(identity) is list and len(identity)==2
            and all(type(v) is int and v >= 0 for v in identity))
    pointers = control['field_pointers']
    _require(type(pointers) is list and bool(pointers) and all(type(p) is str for p in pointers)
        and len(pointers)==len(set(pointers)))
    from ..changes._patch_pointer import _pointer
    for pointer in pointers: _pointer(pointer, '/field_pointers')
    subjects = control['subject_ids']
    _require(subjects is None or (type(subjects) is list and bool(subjects)
        and all(type(v) is str and v for v in subjects) and len(subjects)==len(set(subjects))))
    _require(control['configuration_id'] is None or type(control['configuration_id']) is str)
    _require(control['output'] is None or type(control['output']) is str)
    if control['request'] is not None:
        request = AnalyzerRequest(encoded(control['request']))
        _require(command_id == 'analyzer.run' and control['supplied'] is None
            and request.data['request_id'] == arguments['analysis_id'])
    else:
        _require(control['project'] is not None and type(control['supplied']) is dict)
        request_inputs(encoded(control['supplied']), [item['descriptor']['analyzer_id']
            for item in control['supplied']['analyzers']])
    command = registry.resolve(command_id)
    _require(command.command_class is CommandClass.GENERATED_OUTPUT
        and command.effect_scope is EffectScope.EXTERNAL_OUTPUT
        and command.protocol.work.continuation_supported)
    return dict(command_id=command_id, command_class='generated_output',
        normalized_arguments=decode(encoded(arguments)))


def _absolute(value):
    from .root import _path
    _path(value)


def prepare_analyzer_work(invocation):
    options, resolved = invocation.options, invocation.resolved
    cwd = resolved.working_directory
    guards = []
    def read(path):
        source = InputFile(path, cwd)
        document = decode(source.raw)
        guards.append(dict(path=str(source.path), document=document, raw_hex=source.raw.hex()))
        source.current()
        return document
    # Allocate exactly once, before reading any project snapshot/construction input.
    # Explicit complete requests own their data ID and never generate a new one.
    explicit = read(options['--request']) if '--request' in options else None
    identity = (AnalysisRequestId(AnalyzerRequest(encoded(explicit)).data['request_id'])
        if explicit is not None else prepare_analysis_id(options.get('--analysis-id')))
    root = resolved.project_root
    supplied = None
    if explicit is None:
        require(root is not None and bool(options.get('--analyzer')),
            'analyzer_selection_required', exit_code=2)
        raw = (read(options['--inputs']) if '--inputs' in options
            else default_inputs(read(str(root/'specroad.json'))))
        supplied = request_inputs(encoded(raw), options['--analyzer'])
    output = options.get('--output')
    control = dict(format_version='analyzer-work-request-v1', project=None if root is None else str(root),
        supplied=supplied, subject_ids=None if '--subject' not in options else list(options['--subject']),
        field_pointers=list(options.get('--field', ('/statement',))),
        configuration_id=resolved.values.get('configuration'), request=explicit, guards=guards,
        output=output, output_root=options.get('--output-root'), cwd=str(cwd),
        project_identity=None if root is None else [os.stat(root).st_dev,os.stat(root).st_ino])
    from ..changes._patch_pointer import _pointer
    from ..model.errors import ModelError
    from ..analyzers._values import AnalyzerError
    pointers = control['field_pointers']
    require(bool(pointers) and len(pointers)==len(set(pointers)), 'analyzer_invalid_pointer_selection', exit_code=2)
    try:
        for pointer in pointers: _pointer(pointer, '/field_pointers')
    except ModelError as error:
        raise AnalyzerError(error.reason, pointer=error.pointer, exit_code=2) from error
    require(control['subject_ids'] is None or (bool(control['subject_ids'])
        and len(control['subject_ids'])==len(set(control['subject_ids']))), 'analyzer_duplicate_selection', exit_code=2)
    arguments = dict(analysis_id=identity.value, construction=control)
    command = command_binding(invocation.registry, invocation.command.command_id, arguments)
    return _create_manifest(invocation.registry, command, tool_build=_runtime_build(),
        source_bindings=dict(project_id=None, scope=[], model_root_sha256=None),
        inputs=[dict(root_id='analyzer', path=CONTROL, raw=encoded(control))],
        units=units(None, invocation.command.command_id))


def units(request, command_id):
    return [dict(key='snapshot', phase='snapshot', range={'complete_request': True}),
            dict(key='finalize', phase='finalize', range={'command_id':command_id})]


def _inputs(value, objects):
    from .manifest import _entries
    rows = _entries('inputs', value['manifests']['inputs'], objects)
    _require(all(row['root_id'] == 'analyzer' for row in rows))
    return {row['path']: _bytes({k:row[k] for k in ('sha256','size')}, objects) for row in rows}


def request_of(value, objects):
    raw = _inputs(value, objects).get(SNAPSHOT)
    return None if raw is None else AnalyzerRequest(raw)


def checked_value(value, objects, registry):
    """Validate the closed analyzer plan and every retained completion."""
    from .manifest import _entries
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
            _require(request is not None and evidence == {'request_sha256':sha256(request.canonical_bytes).hexdigest()})
        elif task['key'] == 'finalize':
            _require(request is not None and evidence == {'prepared':True})
        done[task['key']] = evidence
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
        complete = [{'unit_id':tasks[0]['unit_id'], 'evidence':_put(encoded({'request_sha256':sha256(request.canonical_bytes).hexdigest()}),objects)}]
        value['checkpoint_generation'] += 1
        return _partition(value,tasks,complete,objects,manifest._registry,value['tool_build'])
    if manifest.entries('remaining'):
        task = manifest.entries('remaining')[0]
        return partition_work_manifest(manifest, {task['unit_id']: encoded({'prepared':True})})
    result = request if value['command_id'] == 'analyzer.request' else unavailable_package(request)
    return complete_work_manifest(manifest, result.data, exit_code=0 if value['command_id']=='analyzer.request' else 5)


def check_outcome(value, objects, document, exit_code):
    request = request_of(value, objects)
    _require(request is not None)
    if value['command_id'] == 'analyzer.request':
        expected = request
    else:
        from ..analyzers.packages import ReportPackage
        package = ReportPackage(encoded(document), request=request)
        expected = unavailable_package(request, run_ids={
            report.data['analyzer']['descriptor']['analyzer_id']:report.data['run_id']
            for report in package.reports})
    _require(encoded(document) == expected.canonical_bytes
        and type(exit_code) is int and exit_code == (0 if value['command_id']=='analyzer.request' else 5))


def outcome(manifest):
    from ._completion import read_completion
    value = manifest.as_dict()
    require(value['state'] == 'completed', 'analyzer_work_incomplete', exit_code=6)
    record = read_completion(value, manifest.objects, manifest._registry)
    return record['outcome'], record['exit_code']


def resume_analyzer_work(store, *, max_units=1):
    from .control import _initial
    from .resume import _runtime_build
    require(type(max_units) is int and max_units > 0, 'analyzer_work_unit_count', exit_code=2)
    _initial(store, _runtime_build())
    current = store.read()
    require(current is not None, 'analyzer_work_checkpoint_missing', exit_code=5)
    for _ in range(max_units):
        if current.as_dict()['state'] == 'completed': break
        current = store._update(advance)
    return current
