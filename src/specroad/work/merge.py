"""Finite complete passive merge work on the native immutable checkpoint store."""
from hashlib import sha256

from ..cli.requests import CommandRequest
from ..model.canonical import canonical_json_bytes as jcs
from ..model._schema import validate_builtin
from ..storage.json_syntax import parse_json_object as parsed
from ..migration.plan_values import b64, unb64, file_bindings
from ..merge.preparation import (PHASES, capture_preparation, calculate, phase_result,
                                 outcome, result_schema)
from ._data_contract import _object, _hash
from ._request_binding import _command
from .manifest import _create_manifest, partition_work_manifest, complete_work_manifest, _bytes
from .resume import _runtime_build, WorkResumeError
from .control import _initial
from ._completion import read_completion

ADAPTER = 'merge-work-v1'
BLOCK = 65536


def require(ok, reason):
    if not ok:
        raise WorkResumeError(reason)


def _units(bindings):
    result = []
    for role in ('base', 'ours', 'theirs'):
        for entry in bindings[role]['resources']:
            size = entry['size']
            for offset in range(0, size, BLOCK) if size else (0,):
                result.append({'key': role+':'+entry['path']+':'+str(offset), 'phase': 'input_integrity',
                    'range': {'adapter': ADAPTER, 'role': role, 'path': entry['path'],
                              'offset': offset, 'length': min(BLOCK, size-offset)}})
    result.extend({'key': phase, 'phase': phase, 'range': {'adapter': ADAPTER}}
                  for phase in (*PHASES, 'finalize'))
    return result


def prepare_merge_work(registry, sources, *, plan_id, history, plan_raw=None,
                       expected_plan_sha256=None, fail_on_change=False):
    require(type(fail_on_change) is bool, 'merge_work_flag_invalid')
    inputs = capture_preparation(sources, plan_id=plan_id, history=history,
        plan_raw=plan_raw, expected_plan_sha256=expected_plan_sha256)
    bindings = {role: row['binding'] for role, row in inputs['sources'].items()}
    descriptor = {key: value for key, value in inputs.items() if key != 'sources'}
    descriptor.update(adapter=ADAPTER, bindings=bindings, fail_on_change=fail_on_change)
    payloads = [{'root_id': role, 'path': row['path'], 'raw': unb64(row['bytes_base64'])}
                for role, source in inputs['sources'].items() for row in source['files']]
    payloads.append({'root_id': 'control', 'path': 'request.json', 'raw': jcs(descriptor)})
    command = _command(registry, CommandRequest('merge.plan'), planning=True)
    return _create_manifest(registry, command, tool_build=_runtime_build(),
        source_bindings={'project_id': sources.ours.project_id, 'scope': ['project'],
                         'model_root_sha256': bindings['ours']['model_root_sha256']},
        inputs=payloads, units=_units(bindings))


def checked(current):
    """Check complete input closure and prefix data without rerunning merge phases."""
    value = current.as_dict()
    require(value['command_id'] == 'merge.plan' and value['command_class'] == 'plan_output'
        and value['normalized_arguments'] == {'arguments': {}, 'options': {}}
        and value['state'] in ('running', 'completed'), 'merge_work_request_changed')
    rows = {(row['root_id'], row['path']): current.objects[row['sha256']]
            for row in current.entries('inputs')}
    require(('control', 'request.json') in rows, 'merge_work_inputs_missing')
    descriptor = parsed(rows['control', 'request.json'])
    _object(descriptor, ('format_version', 'plan_id', 'history', 'plan_bytes_base64',
                        'plan_sha256', 'adapter', 'bindings', 'fail_on_change'))
    require(descriptor['format_version'] == 'merge-preparation-input-v1'
        and descriptor['adapter'] == ADAPTER and type(descriptor['fail_on_change']) is bool,
        'merge_work_adapter_changed')
    from ..merge.inventory import _plan_id
    _plan_id(descriptor['plan_id'])
    require(type(descriptor['history']) is dict, 'merge_work_history_invalid')
    _object(descriptor['bindings'], ('base', 'ours', 'theirs'))
    expected = {('control', 'request.json')}
    sources = {}
    for role in ('base', 'ours', 'theirs'):
        binding = descriptor['bindings'][role]
        files = {path: raw for (kind, path), raw in rows.items() if kind == role}
        require(type(binding) is dict and files and jcs({'rows': binding.get('resources')}) == jcs({'rows': file_bindings(files)}),
                'merge_work_source_files_changed')
        expected.update((role, path) for path in files)
        sources[role] = {'binding': binding,
            'files': [{'path': path, 'bytes_base64': b64(raw)} for path, raw in sorted(files.items())]}
    require(set(rows) == expected, 'merge_work_input_inventory_changed')
    raw = descriptor['plan_bytes_base64']
    if raw is None:
        require(descriptor['plan_sha256'] is None, 'merge_work_plan_changed')
    else:
        _hash(descriptor['plan_sha256'])
        require(sha256(unb64(raw)).hexdigest() == descriptor['plan_sha256'], 'merge_work_plan_changed')
    ours = descriptor['bindings']['ours']
    require(value['source_bindings'] == {'project_id': ours.get('project_id'), 'scope': ['project'],
        'model_root_sha256': ours.get('model_root_sha256')}, 'merge_work_source_binding_changed')
    tasks = current.entries('tasks'); done = current.entries('completed')
    require(jcs([{k: v for k, v in row.items() if k != 'unit_id'} for row in tasks]) == jcs(_units(descriptor['bindings'])),
            'merge_work_task_plan_changed')
    require([r['unit_id'] for r in done] == [t['unit_id'] for t in tasks[:len(done)]],
            'merge_work_nonprefix_progress')
    results = {}
    for task, entry in zip(tasks, done):
        record = parsed(_bytes(entry['evidence'], current.objects))
        _object(record, ('adapter', 'phase', 'result'))
        require(record['adapter'] == ADAPTER and record['phase'] == task['phase'], 'merge_work_evidence_changed')
        if task['phase'] == 'input_integrity':
            require(jcs(record['result']) == jcs(_block(task, rows)), 'merge_work_input_evidence_changed')
        else:
            require(type(record['result']) is dict, 'merge_work_phase_result_invalid')
            if task['phase'] == 'comparison':
                selected = record['result']
                require(set(selected) == {'plan_bytes_base64', 'plan_sha256'}, 'merge_work_phase_result_invalid')
                _hash(selected['plan_sha256'])
                require(sha256(unb64(selected['plan_bytes_base64'])).hexdigest() == selected['plan_sha256'],
                        'merge_work_phase_result_invalid')
            results[task['phase']] = record['result']
    inputs = {key: descriptor[key] for key in
        ('format_version', 'plan_id', 'history', 'plan_bytes_base64', 'plan_sha256')}
    inputs['sources'] = sources
    return inputs, descriptor, rows, tasks, done, results


def _block(task, rows):
    part = task['range']
    raw = rows[part['role'], part['path']][part['offset']:part['offset']+part['length']]
    require(len(raw) == part['length'], 'merge_work_input_block_missing')
    return {'size': len(raw), 'sha256': sha256(raw).hexdigest()}


def _final(inputs, results, *, services):
    actual, phases = calculate(inputs, services=services)
    require(jcs({key: results.get(key) for key in PHASES}) == jcs(phases), 'merge_work_phase_recomputation_mismatch')
    return actual


def resume_merge_work(store, *, max_units=1, services=None):
    """Advance a bounded prefix, then independently close the complete result."""
    require(type(max_units) is int and max_units > 0, 'merge_work_units_invalid')
    _initial(store, _runtime_build())
    def advance(current):
        inputs, descriptor, rows, tasks, done, results = checked(current)
        if current.as_dict()['state'] == 'completed':
            _completed(current, inputs, results, services=services)
            return current
        completions = {}
        for task in tasks[len(done):len(done)+max_units]:
            phase = task['phase']
            if phase == 'input_integrity':
                result = _block(task, rows)
            elif phase == 'finalize':
                result = _final(inputs, results, services=services)
            else:
                result = phase_result(inputs, phase, results, services=services)
            results[phase] = result
            completions[task['unit_id']] = jcs({'adapter': ADAPTER, 'phase': phase, 'result': result})
        if completions:
            # A partition and terminal result are distinct immediate native
            # successors; never skip a generation in the durable chain.
            return partition_work_manifest(current, completions)
        if not current.entries('remaining'):
            # Finalize evidence may survive a crash before its terminal checkpoint.
            final = _final(inputs, results, services=services)
            require(jcs(final) == jcs(results['finalize']), 'merge_work_final_result_changed')
            code = 1 if descriptor['fail_on_change'] and final['changed'] is True else 0
            return complete_work_manifest(current, final, exit_code=code)
        return current
    return store._update(advance)


def check_outcome(value, document, exit_code):
    require(value['command_id'] == 'merge.plan' and value['command_class'] == 'plan_output'
            and type(exit_code) is int and exit_code in (0, 1), 'merge_work_outcome_invalid')
    validate_builtin(document, result_schema())
    require(exit_code == 0 or document['changed'] is True, 'merge_work_outcome_invalid')


def _completed(current, inputs, results, *, services):
    final = _final(inputs, results, services=services)
    record = read_completion(current.as_dict(), current.objects, current._registry)
    require(jcs(results.get('finalize')) == jcs(final) == jcs(record['outcome']), 'merge_work_final_result_changed')
    return record


def merge_work_result(store, *, services=None):
    _initial(store, _runtime_build())
    current = store.read()
    inputs, descriptor, _, _, _, results = checked(current)
    require(current.as_dict()['state'] == 'completed', 'merge_work_incomplete')
    record = _completed(current, inputs, results, services=services)
    code = 1 if descriptor['fail_on_change'] and record['outcome']['changed'] is True else 0
    require(record['exit_code'] == code, 'merge_work_result_exit_changed')
    return record['outcome'], code
