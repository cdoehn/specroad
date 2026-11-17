"""Passive Proposal checks over owned native bytes, never stored approval."""
from hashlib import sha256

from ..authoring._inspection_snapshot import InspectionSnapshot
from ..cli.requests import CommandRequest
from ..cli.result_schemas import validate_result_document
from ..migration.plan_values import file_bindings
from ..model.canonical import canonical_json_bytes as jcs
from ..proposals._check_workspace import CheckWorkspace
from ..proposals._validation_input import ProposalInput
from ..proposals.check import check_proposal_project
from ..proposals.project_validation import _preflight
from ..proposals.scope import specification_manifest
from ..proposals.values import ProposalOriginal
from ..storage.json_syntax import parse_json_object as parsed
from ..storage.project import ProjectSource
from ._data_contract import _object, _hash
from ._request_binding import _command
from .manifest import _create_manifest, partition_work_manifest, complete_work_manifest, _bytes
from .resume import _runtime_build, WorkResumeError
from .control import _initial
from ._completion import read_completion

ADAPTER = 'proposal-check-work-v1'
BLOCK = 65536


def require(ok, reason):
    if not ok:
        raise WorkResumeError(reason)


def _units(resources):
    tasks = []
    for role in ('basis', 'proposal'):
        for row in resources[role]:
            for offset in range(0, row['size'], BLOCK) if row['size'] else (0,):
                tasks.append({'key': role+':'+row['path']+':'+str(offset), 'phase': 'input_integrity',
                    'range': {'adapter': ADAPTER, 'role': role, 'path': row['path'],
                        'offset': offset, 'length': min(BLOCK, row['size']-offset)}})
    tasks.extend({'key': phase, 'phase': phase, 'range': {'adapter': ADAPTER}}
                 for phase in ('check', 'finalize'))
    return tasks


def prepare_proposal_work(registry, root, operand, *, cwd=None):
    """Seal coherent complete input bytes before allocating any Work directory."""
    source = ProjectSource(root); _preflight(source)
    supplied = ProposalInput(source, operand, cwd)
    original = supplied.original()
    snapshot = InspectionSnapshot(root, None, include_archive_objects=True)
    basis_hash = specification_manifest(snapshot.model).sha256
    require(basis_hash == original.binding.base_model_root_sha256, 'proposal_work_basis_changed')
    resources = {'basis': file_bindings(snapshot.raw),
                 'proposal': file_bindings({original.path: original.source_bytes})}
    descriptor = dict(adapter=ADAPTER, project_id=source.configuration.project_id,
        basis_sha256=basis_hash, proposal_path=original.path, binding=original.binding.data,
        proposal_sha256=original.sha256, resources=resources)
    inputs = [{'root_id': 'basis', 'path': p, 'raw': b} for p, b in sorted(snapshot.raw.items())]
    inputs.extend(({'root_id': 'proposal', 'path': original.path, 'raw': original.source_bytes},
                   {'root_id': 'control', 'path': 'request.json', 'raw': jcs(descriptor)}))
    command = _command(registry, CommandRequest('proposal.check', arguments={'proposal': original.data['id']}))
    initial = _create_manifest(registry, command, tool_build=_runtime_build(),
        source_bindings={'project_id': descriptor['project_id'], 'scope': ['specification'],
                         'model_root_sha256': basis_hash}, inputs=inputs, units=_units(resources))
    _preflight(source); source.check_current(); supplied.verify_current(); snapshot.verify_current()
    return initial, (source.boundary, supplied.boundary)


def _block(task, rows):
    part = task['range']
    raw = rows[part['role'], part['path']][part['offset']:part['offset']+part['length']]
    require(len(raw) == part['length'], 'proposal_work_block_missing')
    return {'size': len(raw), 'sha256': sha256(raw).hexdigest()}


def _report(result):
    _object(result, ('report', 'exit_code'))
    report, code = result['report'], result['exit_code']
    validate_result_document('proposal-check-v1', report)
    require(type(code) is int and 0 <= code <= 7 and report['passed'] == (code == 0),
            'proposal_work_outcome_invalid')
    require(report['full_semantic_validation'] == report['passed']
        and report['workspace']['retained'] is False and report['workspace']['path'] is None
        and report['workspace']['cleanup'] in ('not_created', 'removed'), 'proposal_work_cleanup_required')
    require(report['result_sha256'] == sha256(jcs({k: v for k, v in report.items()
            if k != 'result_sha256'})).hexdigest(), 'proposal_work_report_hash_changed')


def _semantic(result):
    _report(result)
    value = parsed(jcs(result))
    value['report'].pop('result_sha256')
    value['report']['audit'].pop('started_at'); value['report']['audit'].pop('ended_at')
    return jcs(value)


def checked(current):
    """Validate closed request, all original objects and the completed prefix."""
    value = current.as_dict()
    require(value['command_id'] == 'proposal.check' and value['command_class'] == 'read_only'
            and value['state'] in ('running', 'completed'), 'proposal_work_request_changed')
    rows = {(r['root_id'], r['path']): current.objects[r['sha256']] for r in current.entries('inputs')}
    require(('control', 'request.json') in rows, 'proposal_work_inputs_missing')
    descriptor = parsed(rows['control', 'request.json'])
    _object(descriptor, ('adapter', 'project_id', 'basis_sha256', 'proposal_path', 'binding',
                         'proposal_sha256', 'resources'))
    require(descriptor['adapter'] == ADAPTER and jcs(descriptor) == rows['control', 'request.json'],
            'proposal_work_adapter_changed')
    _hash(descriptor['basis_sha256']); _hash(descriptor['proposal_sha256'])
    _object(descriptor['resources'], ('basis', 'proposal'))
    expected = {('control', 'request.json')}
    for role in ('basis', 'proposal'):
        files = {path: raw for (kind, path), raw in rows.items() if kind == role}
        require(files and jcs(descriptor['resources'][role]) == jcs(file_bindings(files)),
                'proposal_work_resource_binding_changed')
        expected.update((role, path) for path in files)
    require(set(rows) == expected and len(descriptor['resources']['proposal']) == 1,
            'proposal_work_input_inventory_changed')
    key = ('proposal', descriptor['proposal_path'])
    require(key in rows, 'proposal_work_original_missing')
    original = ProposalOriginal(rows[key], path=key[1])
    require(original.sha256 == descriptor['proposal_sha256']
        and original.binding.data == descriptor['binding']
        and original.binding.base_model_root_sha256 == descriptor['basis_sha256'],
            'proposal_work_original_changed')
    require(value['normalized_arguments'] == {'arguments': {'proposal': original.data['id']}, 'options': {}}
        and value['source_bindings'] == {'project_id': descriptor['project_id'], 'scope': ['specification'],
            'model_root_sha256': descriptor['basis_sha256']}, 'proposal_work_source_binding_changed')
    tasks, done = current.entries('tasks'), current.entries('completed')
    require(jcs([{k: v for k, v in row.items() if k != 'unit_id'} for row in tasks])
            == jcs(_units(descriptor['resources'])), 'proposal_work_task_plan_changed')
    require([r['unit_id'] for r in done] == [t['unit_id'] for t in tasks[:len(done)]],
            'proposal_work_nonprefix_progress')
    results = {}
    for task, entry in zip(tasks, done):
        record = parsed(_bytes(entry['evidence'], current.objects))
        _object(record, ('adapter', 'phase', 'result'))
        require(record['adapter'] == ADAPTER and record['phase'] == task['phase'],
                'proposal_work_evidence_changed')
        result = record['result']
        if task['phase'] == 'input_integrity':
            require(jcs(result) == jcs(_block(task, rows)), 'proposal_work_block_changed')
        else:
            _report(result)
            require(result['report']['binding'] == descriptor['binding']
                and result['report']['proposal_sha256'] == descriptor['proposal_sha256'],
                    'proposal_work_check_binding_changed')
            results[task['phase']] = result
    return descriptor, rows, tasks, done, results


def _calculate(store, descriptor, rows, services):
    workspace = CheckWorkspace(store._location.path, False, guard=store._location._outside)
    try:
        workspace.create()
        files = {path: raw for (kind, path), raw in rows.items() if kind == 'basis'}
        root = workspace.materialize('basis', files)
        snapshot = InspectionSnapshot(root, None, include_archive_objects=True)
        require(snapshot.raw == files and snapshot.model.configuration.project_id == descriptor['project_id']
            and specification_manifest(snapshot.model).sha256 == descriptor['basis_sha256'],
                'proposal_work_basis_changed')
        operand = workspace.materialize('operand', {'original.json': rows['proposal', descriptor['proposal_path']]})
        result = check_proposal_project(root, str(operand/'original.json'), services=services)
        snapshot.verify_current(); workspace.verify()
        outcome = {'report': result.as_dict()['result'], 'exit_code': result.exit_code}
        _report(outcome)
        require(outcome['report']['binding'] == descriptor['binding']
            and outcome['report']['proposal_sha256'] == descriptor['proposal_sha256'],
                'proposal_work_check_binding_changed')
        return outcome
    finally:
        workspace.close()


def _final(store, descriptor, rows, results, services):
    actual = _calculate(store, descriptor, rows, services)
    require('check' in results and _semantic(actual) == _semantic(results['check']),
            'proposal_work_check_recomputation_mismatch')
    return results['check']  # Preserve the original audit, not a new claimed review.


def resume_proposal_work(store, *, max_units=1, services=None):
    require(type(max_units) is int and max_units > 0, 'proposal_work_units_invalid')
    _initial(store, _runtime_build())
    def advance(current):
        descriptor, rows, tasks, done, results = checked(current)
        if current.as_dict()['state'] == 'completed':
            _completed(store, current, descriptor, rows, results, services)
            return current
        completions = {}
        for task in tasks[len(done):len(done)+max_units]:
            phase = task['phase']
            result = (_block(task, rows) if phase == 'input_integrity' else
                      _calculate(store, descriptor, rows, services) if phase == 'check' else
                      _final(store, descriptor, rows, results, services))
            results[phase] = result
            completions[task['unit_id']] = jcs({'adapter': ADAPTER, 'phase': phase, 'result': result})
        if completions:
            return partition_work_manifest(current, completions)
        final = _final(store, descriptor, rows, results, services)
        require(jcs(final) == jcs(results.get('finalize')), 'proposal_work_final_result_changed')
        return complete_work_manifest(current, final, exit_code=final['exit_code'])
    return store._update(advance)


def check_outcome(value, document, exit_code):
    require(value['command_id'] == 'proposal.check' and value['command_class'] == 'read_only',
            'proposal_work_outcome_invalid')
    _report(document)
    require(type(exit_code) is int and exit_code == document['exit_code'], 'proposal_work_exit_changed')


def _completed(store, current, descriptor, rows, results, services):
    actual = _final(store, descriptor, rows, results, services)
    record = read_completion(current.as_dict(), current.objects, current._registry)
    require(jcs(actual) == jcs(results.get('finalize')) == jcs(record['outcome']),
            'proposal_work_final_result_changed')
    return record


def proposal_work_result(store, *, services=None):
    _initial(store, _runtime_build())
    current = store.read()
    descriptor, rows, _, _, results = checked(current)
    require(current.as_dict()['state'] == 'completed', 'proposal_work_incomplete')
    record = _completed(store, current, descriptor, rows, results, services)
    return record['outcome']['report'], record['exit_code']
