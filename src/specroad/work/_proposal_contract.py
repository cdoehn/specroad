"""Closed passive Work data, separate from execution and Proposal lifecycle."""
from datetime import datetime
from hashlib import sha256

from ..cli.result_schemas import validate_result_document
from ..migration.plan_values import file_bindings
from ..model.audit_values import UtcTimestamp
from ..model.canonical import canonical_json_bytes as jcs
from ..proposals.values import ProposalOriginal
from ..storage.json_syntax import parse_json_object as parsed
from ._data_contract import _object, _hash
from .manifest import _bytes
from .resume import WorkResumeError

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
    audit = report['audit']
    UtcTimestamp(audit['started_at']); UtcTimestamp(audit['ended_at'])
    require(datetime.fromisoformat(audit['ended_at'].replace('Z', '+00:00')) >=
            datetime.fromisoformat(audit['started_at'].replace('Z', '+00:00')),
            'proposal_work_audit_time_invalid')
    require(audit['outcome'] == ('passed' if report['passed'] else 'failed')
        and report['binding'] is not None and audit['proposal_id'] == report['binding']['proposal_id'],
            'proposal_work_audit_binding_changed')
    if code == 0:
        require(report['context_sha256'] is not None and report['target_model_root_sha256'] is not None
            and report['target_sources_sha256'] is not None
            and set(report['checks']) == {'validation', 'lint', 'diff', 'impact', 'queries', 'renders'},
                'proposal_work_complete_check_required')
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
