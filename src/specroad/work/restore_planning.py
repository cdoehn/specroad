"""Separate source capture, inventory, global qualification and plan delivery.

Completed captures retain original bytes. A later step never replaces them
with a new source or invents a valid base model for the damaged project.
"""
from base64 import b64encode, b64decode

from ..cli._restore_options import restore_request
from ..cli.requests import CommandRequest
from ..model.canonical import canonical_json_bytes
from ..recovery._captured_plan import captured_plan
from ..recovery._codec import file_row, safe_path
from ..recovery._coverage import inventory_roots
from ..recovery._current_evidence import BASELINES
from ..recovery._inventory import boundary, observe, read_source
from ..recovery._observations import observe_configuration, verify_live
from ..recovery._sources import reconstruct
from ..recovery._validation import project_bytes
from ..recovery.files import publish_restore_plan
from ..recovery.values import RestorePlan, RestoreError, guarded, persisted_contract, require
from ..storage.json_syntax import parse_json_object
from ._request_binding import _command
from .manifest import (_create_manifest, _bytes, complete_work_manifest,
                       partition_work_manifest)
from .restore_execution import _build
from .result_files import _publish_file, _verify_files, _ensure_work
from ._public_errors import work_errors


_PHASES = ('source_capture', 'inventory_capture', 'qualify_plan', 'deliver_plan')
_SOURCES = {'project_id': None, 'scope': ['project'], 'model_root_sha256': None}


def _units():
    return [{'key': name, 'phase': name,
             'range': {'adapter': 'native-restore-planning-work-v1'}} for name in _PHASES]


def check_binding(value, inputs):
    require(all(value[name] is None for name in
                ('actor', 'request_id', 'operations_sha256', 'plan_binding'))
            and value['source_bindings'] == _SOURCES and not inputs,
            'restore_planning_work_binding_invalid')


@guarded
def prepare_planning_work(registry, request):
    request = restore_request(request)
    require('--from' in request.options, 'restore_planning_work_required', exit_code=2)
    from ._restore_capture import declarations
    command = _command(registry, request, recovery=True)
    return _create_manifest(registry, command, tool_build=_build(),
                            source_bindings=_SOURCES, inputs=[], units=declarations(request.options))


def _operational(options):
    return ({'default_locale': options['--default-locale'],
             'generated_path': options['--generated-path']}
            if options['--source-kind'] == 'baseline' else None)


def _pack(files):
    return [{**file_row(path, raw), 'data_base64': b64encode(raw).decode('ascii')}
            for path, raw in sorted(files.items(), key=lambda item: item[0].encode())]


def _unpack(rows):
    require(type(rows) is list, 'restore_work_snapshot_invalid')
    files = {}
    for row in rows:
        require(type(row) is dict and set(row) == {'path', 'size', 'sha256', 'data_base64'},
                'restore_work_snapshot_invalid')
        safe_path(row['path'])
        raw = b64decode(row['data_base64'], validate=True)
        require(b64encode(raw).decode('ascii') == row['data_base64']
                and file_row(row['path'], raw) == {key: row[key] for key in ('path', 'size', 'sha256')}
                and row['path'] not in files, 'restore_work_snapshot_invalid')
        files[row['path']] = raw
    require(_pack(files) == rows, 'restore_work_snapshot_invalid')
    return files


def _source(options, evidence):
    files = _unpack(evidence['files'])
    require(options['--from'] in files, 'restore_work_source_missing')
    raw = files.pop(options['--from'])
    used = {}
    def read(path):
        require(path in files, 'restore_work_source_missing', path=path)
        used[path] = files[path]
        return files[path]
    model_files, _, _, root, _ = reconstruct(options['--source-kind'], raw, read,
                                            operational=_operational(options))
    require(used == files, 'restore_dependency_inventory_mismatch')
    model, actual_root = project_bytes(model_files)
    require(root == actual_root, 'restore_source_root_mismatch')
    return raw, files, model


def _plan(options, evidence, *, qualify=False, services=None):
    raw, dependencies, _ = _source(options, evidence[0])
    return captured_plan(options['--project'], source_root=options['--source-root'],
        source_path=options['--from'], source_kind=options['--source-kind'],
        source_bytes=raw, dependencies=dependencies, inventory=evidence[1]['inventory'],
        current=_unpack(evidence[1]['files']), operational=_operational(options),
        qualify=qualify, services=services)


def checked(current):
    value = current.as_dict()
    return _checked(value, current.objects, current.entries('tasks'), current.entries('completed'))


def _checked(value, objects, tasks, completed):
    request = restore_request(CommandRequest(value['command_id'], **value['normalized_arguments']))
    require('--from' in request.options and value['tool_build'] == _build(),
            'restore_planning_work_required', exit_code=6)
    if tasks and tasks[0]['range'].get('adapter') == 'native-restore-planning-capture-v1':
        return _checked_capture(value, objects, tasks, completed, request.options)
    require([{key: unit[key] for key in ('key', 'phase', 'range')}
             for unit in tasks] == _units(),
            'restore_planning_work_units_invalid')
    require([row['unit_id'] for row in completed]
            == [row['unit_id'] for row in tasks[:len(completed)]],
            'restore_planning_work_progress_invalid')
    evidence = [parse_json_object(_bytes(row['evidence'], objects)) for row in completed]
    fields = ({'files'}, {'inventory', 'files'}, {'plan'}, {'result'})
    for index, record in enumerate(evidence):
        require(set(record) == {'phase', 'work_id'} | fields[index]
                and record['phase'] == _PHASES[index]
                and record['work_id'] == value['work_id'], 'restore_planning_work_progress_invalid')
    if evidence:
        _source(request.options, evidence[0])
    if len(evidence) >= 2:
        plan = _plan(request.options, evidence)
        if len(evidence) >= 3:
            require(plan.data == evidence[2]['plan'], 'restore_planning_work_plan_changed', exit_code=6)
        if len(evidence) == 4:
            require(result_document(plan, request.options) == evidence[3]['result'],
                    'restore_planning_work_result_changed', exit_code=6)
    return request.options, evidence


def final_outcome(value, objects, document, exit_code):
    from .manifest import _entries
    completed = _entries('completed', value['manifests']['completed'], objects)
    tasks = _entries('tasks', value['manifests']['tasks'], objects)
    require(len(completed) == len(tasks) and exit_code == 0,
            'restore_planning_work_incomplete')
    options, evidence = _checked(value, objects, tasks, completed)
    saved = evidence[-1]
    require(saved['phase'] == 'deliver_plan' and saved['work_id'] == value['work_id']
            and saved['result'] == document, 'restore_planning_work_result_changed', exit_code=6)
    plan = RestorePlan(canonical_json_bytes(document['restore_plan']))
    require(document == result_document(plan, options), 'restore_planning_work_result_changed', exit_code=6)


def result_document(plan, options):
    return {'format_version': 'restore-command-v1', 'mode': 'plan',
        'restore_plan': plan.data, 'execution': None,
        'plan_file': {'root': options['--output-root'], 'path': options['--output'],
                     'size': len(plan.source_bytes), 'sha256': plan.sha256},
        'history_assessments': list(plan.history_assessments)}


@guarded
@persisted_contract
@work_errors
def resume_planning_work(store, *, services=None):
    """Confirm one real phase; there is no loop and no project write."""
    build = _build()
    # Terminal replay is an observation, including when the original project
    # or source no longer exists. Do not acquire a writer lease for it.
    with store._location.inspect_checkpoint() as held:
        pointer = store._pointer(held)
        require(pointer is not None, 'restore_published_work_required', exit_code=5)
        current = store._read_chain(held, pointer[0])
        if current.as_dict()['state'] == 'completed':
            checked(current)
            value = current.as_dict()
            document = parse_json_object(_bytes(value['result_parts'][0], current.objects))['outcome']
            _verify_files(held, [('restore-plan.json', canonical_json_bytes(document['restore_plan']))])
            _ensure_work(store, held, pointer, current, build)
            return current, document
    with store._location.for_checkpoint() as held:
        pointer = store._pointer(held)
        require(pointer is not None, 'restore_published_work_required', exit_code=5)
        current = store._read_chain(held, pointer[0])
        options, evidence = checked(current)
        value = current.as_dict()
        require(value['state'] in ('running', 'completed'), 'restore_work_cancelled', exit_code=6)
        def ensure():
            _ensure_work(store, held, pointer, current, build)
        if value['state'] == 'completed':
            document = parse_json_object(_bytes(value['result_parts'][0], current.objects))['outcome']
            _verify_files(held, [('restore-plan.json', canonical_json_bytes(document['restore_plan']))])
            ensure()
            return current, document
        tasks = current.entries('tasks')
        if tasks[0]['range'].get('adapter') == 'native-restore-planning-capture-v1':
            return _resume_capture(store, held, pointer, current, options, evidence, ensure, services)
        index = len(evidence)
        if index == len(_PHASES):
            # Publication of the delivery checkpoint may survive a crash
            # before the independent terminal checkpoint. Preserve that prefix.
            document = evidence[-1]['result']
            _qualify_terminal_recovery(document, options, services)
            _verify_files(held, [('restore-plan.json', canonical_json_bytes(document['restore_plan']))], sync=True)
            ensure()
            current = store._publish_held(held,
                complete_work_manifest(current, document, exit_code=0), pointer)
            pointer = store._pointer(held)
            ensure()
            return current, document
        record = {'phase': _PHASES[index], 'work_id': value['work_id']}
        if index == 0:
            origin = boundary(options['--source-root'])
            captured = {options['--from']: read_source(origin, options['--from'])}
            def read(path):
                raw = read_source(origin, path)
                require(path not in captured or captured[path] == raw, 'restore_source_changed', exit_code=6)
                captured[path] = raw
                return raw
            reconstruct(options['--source-kind'], captured[options['--from']], read,
                        operational=_operational(options))
            record['files'] = _pack(captured)
            _source(options, record)
            for path, raw in captured.items():
                require(read_source(origin, path) == raw, 'restore_source_changed', exit_code=6)
        elif index == 1:
            _, _, model = _source(options, evidence[0])
            project = boundary(options['--project'])
            configuration, initial, baselines = observe_configuration(project)
            inventory, files = observe(project, inventory_roots(model.configuration, configuration))
            require(all(files.get(path) == raw for path, raw in initial.items()),
                    'restore_inventory_changed', exit_code=6)
            if baselines is not None:
                require([row for row in inventory['entries'] if row['path'] == BASELINES
                         or row['path'].startswith(BASELINES + '/')] == baselines['entries'],
                        'restore_inventory_changed', exit_code=6)
            record.update(inventory=inventory, files=_pack(files))
        elif index == 2:
            plan = _plan(options, evidence, qualify=True, services=services)
            verify_live(plan, boundary(options['--project']), boundary(options['--source-root']))
            record['plan'] = plan.data
        else:
            plan = RestorePlan(canonical_json_bytes(evidence[2]['plan']))
            # A retry may encounter the exact external bytes published before
            # its checkpoint. It never overwrites even an equal file.
            try:
                publish_restore_plan(plan.source_bytes, output_root=options['--output-root'],
                                     output=options['--output'], services=services)
            except RestoreError as error:
                if error.reason != 'restore_output_exists':
                    raise
                require(read_source(boundary(options['--output-root']), options['--output'])
                        == plan.source_bytes, 'restore_output_changed', exit_code=6)
                from ..recovery._plan_checks import qualify_plan
                qualify_plan(plan, services=services)
                verify_live(plan, boundary(options['--project']), boundary(options['--source-root']))
            _publish_file(held, 'restore-plan.json', plan.source_bytes, ensure)
            _verify_files(held, [('restore-plan.json', plan.source_bytes)], sync=True)
            record['result'] = result_document(plan, options)
        ensure()
        unit = current.entries('tasks')[index]['unit_id']
        candidate = partition_work_manifest(current, {unit: canonical_json_bytes(record)})
        current = store._publish_held(held, candidate, pointer)
        pointer = store._pointer(held)
        if index == 3:
            current = store._publish_held(held,
                complete_work_manifest(current, record['result'], exit_code=0), pointer)
            pointer = store._pointer(held)
            ensure()
            return current, record['result']
        ensure()
        return current, None


def _capture_plan(options, tasks, evidence, *, qualify=False, services=None):
    from ._restore_capture import assembled
    roots = tasks[-1]['range']['roots']
    source, current, inventory = assembled(tasks[:-2], evidence[:len(tasks)-2], roots)
    return _plan(options, [{'files': _pack(source)},
                          {'files': _pack(current), 'inventory': inventory}],
                 qualify=qualify, services=services)


def _checked_capture(value, objects, tasks, completed, options):
    from ._restore_capture import checked_units, chunk_bytes
    checked_units(tasks, options)
    require([row['unit_id'] for row in completed] ==
            [row['unit_id'] for row in tasks[:len(completed)]],
            'restore_planning_work_progress_invalid')
    evidence = [parse_json_object(_bytes(row['evidence'], objects)) for row in completed]
    for task, record in zip(tasks, evidence):
        phase = task['phase']
        field = 'plan' if phase == 'qualify_plan' else 'result' if phase == 'deliver_plan' else 'chunk'
        require(set(record) == {'phase', 'work_id', field} and record['phase'] == phase
                and record['work_id'] == value['work_id'], 'restore_planning_work_progress_invalid')
        if field == 'chunk':
            chunk_bytes(task, record['chunk'])
    if len(evidence) >= len(tasks) - 1:
        plan = _capture_plan(options, tasks, evidence)
        require(plan.data == evidence[len(tasks)-2]['plan'],
                'restore_planning_work_plan_changed', exit_code=6)
        if len(evidence) == len(tasks):
            require(result_document(plan, options) == evidence[-1]['result'],
                    'restore_planning_work_result_changed', exit_code=6)
    return options, evidence



def _qualify_terminal_recovery(document, options, services):
    # Delivery without the independent terminal checkpoint is unfinished Work.
    # It has no passive-replay exemption from current native qualification.
    from ..recovery._plan_checks import qualify_plan
    plan = RestorePlan(canonical_json_bytes(document['restore_plan']))
    qualify_plan(plan, services=services)
    verify_live(plan, boundary(options['--project']), boundary(options['--source-root']))


def _resume_capture(store, held, pointer, current, options, evidence, ensure, services):
    from ._restore_capture import capture
    tasks = current.entries('tasks')
    index = len(evidence)
    if index == len(tasks):
        document = evidence[-1]['result']
        _qualify_terminal_recovery(document, options, services)
        _verify_files(held, [('restore-plan.json', canonical_json_bytes(document['restore_plan']))], sync=True)
        ensure()
        current = store._publish_held(held, complete_work_manifest(current, document, exit_code=0), pointer)
        return current, document
    task = tasks[index]
    phase = task['phase']
    record = {'phase': phase, 'work_id': current.as_dict()['work_id']}
    if phase in ('source_capture', 'inventory_capture'):
        record['chunk'] = capture(options, task)
    elif phase == 'qualify_plan':
        plan = _capture_plan(options, tasks, evidence, qualify=True, services=services)
        verify_live(plan, boundary(options['--project']), boundary(options['--source-root']))
        record['plan'] = plan.data
    else:
        plan = RestorePlan(canonical_json_bytes(evidence[-1]['plan']))
        try:
            publish_restore_plan(plan.source_bytes, output_root=options['--output-root'],
                                 output=options['--output'], services=services)
        except RestoreError as error:
            if error.reason != 'restore_output_exists':
                raise
            require(read_source(boundary(options['--output-root']), options['--output'])
                    == plan.source_bytes, 'restore_output_changed', exit_code=6)
            from ..recovery._plan_checks import qualify_plan
            qualify_plan(plan, services=services)
            verify_live(plan, boundary(options['--project']), boundary(options['--source-root']))
        _publish_file(held, 'restore-plan.json', plan.source_bytes, ensure)
        _verify_files(held, [('restore-plan.json', plan.source_bytes)], sync=True)
        record['result'] = result_document(plan, options)
    ensure()
    candidate = partition_work_manifest(current, {task['unit_id']: canonical_json_bytes(record)})
    current = store._publish_held(held, candidate, pointer)
    if phase == 'deliver_plan':
        pointer = store._pointer(held)
        current = store._publish_held(held, complete_work_manifest(current, record['result'], exit_code=0), pointer)
        return current, record['result']
    return current, None
