"""Native finite migration preparation/verification on the common Work store.

Only bytes and explicit authoring inputs are portable. The final writer receives
fresh host authority and live paths separately; no provider comes from Work.
"""
from hashlib import sha256

from ..cli.contracts import CommandClass, EffectScope, PreflightProfile
from ..cli.requests import CommandRequest
from ..cli.registry import CommandRegistry
from ..model.canonical import canonical_json_bytes as jcs
from ..storage.json_syntax import parse_json_object as parsed
from ..bundles.migration_source import verify_source_backup
from ..migration.plan_values import require, owned_files
from ..migration.plan_recheck import recheck_migration_plan
from ..migration.planning import plan_migration
from ..migration.transaction_target import materialized_files
from ..migration.verification import verify_migration
from ..changes.values import ChangePlan
from .manifest import (_create_manifest, partition_work_manifest, complete_work_manifest)
from ._request_binding import _command
from ._data_contract import _object
from .control import _initial
from .resume import _runtime_build
from ._completion import read_completion

_ADAPTER = 'migration-work-v1'
_PHASES = ('source', 'plan', 'verify')
_PLANNING = ('inputs', 'actor', 'planned_at', 'change_plan_id', 'request_id', 'target_version')
_BINDINGS = ('expected_backup_sha256', 'expected_source_files_sha256', 'expected_plan_sha256',
             'expected_inputs_sha256', 'expected_report_sha256', 'expected_target_version')


def _request(registry, request):
    require(type(registry) is CommandRegistry and type(request) is CommandRequest
            and request.command_id in ('migrate.plan', 'migrate.verify')
            and not request.arguments and not request.options, 'migration_work_request_required', exit_code=2)
    invocation = registry.bind_request(request); command = invocation.command
    planning = request.command_id == 'migrate.plan'
    require(command.words == ('migrate', 'plan' if planning else 'verify')
        and command.preflight_profile is PreflightProfile.INPUT_READ
        and command.command_class is (CommandClass.PLAN_OUTPUT if planning else CommandClass.READ_ONLY)
        and command.effect_scope is (EffectScope.EXTERNAL_OUTPUT if planning else EffectScope.NONE),
        'migration_work_registered_contract_required', exit_code=2)
    return _command(registry, request, planning=planning)


def _units():
    return [{'key': phase, 'phase': phase, 'range': {'adapter': _ADAPTER, 'index': index}}
            for index, phase in enumerate(_PHASES)]


def _prepare(registry, request, backup_raw, descriptor, target=None, plan_raw=None, report_raw=None):
    command = _request(registry, request); build = _runtime_build()
    backup = verify_source_backup(backup_raw, expected_sha256=descriptor['backup_sha256'],
        expected_source_files_sha256=descriptor['source_files_sha256'])
    inputs = [{'root_id': 'control', 'path': 'request.json', 'raw': jcs(descriptor)},
              {'root_id': 'source', 'path': 'source.zip', 'raw': backup_raw}]
    if command['command_id'] == 'migrate.verify':
        inputs += [{'root_id': 'plan', 'path': 'plan.json', 'raw': plan_raw},
                   {'root_id': 'plan', 'path': 'report.json', 'raw': report_raw}]
        inputs += [{'root_id': 'target', 'path': p, 'raw': raw}
                   for p, raw in owned_files(target, passive=True).items()]
    sources = {'project_id': backup.manifest['project_id'], 'scope': ['project'],
               'model_root_sha256': backup.manifest['source_model_root_sha256']}
    return _create_manifest(registry, command, tool_build=build,
        source_bindings=sources, inputs=inputs, units=_units())


def prepare_migration_planning_work(registry, request, backup_raw, *,
        expected_backup_sha256, expected_source_files_sha256, **planning):
    """Capture every authoring input; native planning runs in the later plan phase."""
    _object(planning, _PLANNING)
    require(type(request) is CommandRequest and request.command_id == 'migrate.plan',
            'migration_planning_request_required', exit_code=2)
    descriptor = {'adapter': _ADAPTER, 'mode': 'plan', 'backup_sha256': expected_backup_sha256,
        'source_files_sha256': expected_source_files_sha256, 'planning': planning}
    return _prepare(registry, request, backup_raw, descriptor)


def prepare_migration_verification_work(registry, request, backup_raw, plan_raw,
        report_raw, target_files, **bindings):
    """Retain a complete target byte observation; no future live-root claim."""
    _object(bindings, _BINDINGS)
    require(type(request) is CommandRequest and request.command_id == 'migrate.verify',
            'migration_verification_request_required', exit_code=2)
    descriptor = {'adapter': _ADAPTER, 'mode': 'verify',
        'backup_sha256': bindings['expected_backup_sha256'],
        'source_files_sha256': bindings['expected_source_files_sha256'], 'bindings': bindings}
    return _prepare(registry, request, backup_raw, descriptor, target_files, plan_raw, report_raw)


def _inputs(current):
    value = current.as_dict()
    request = CommandRequest(value['command_id'], **value['normalized_arguments'])
    _request(current._registry, request)
    rows = {(r['root_id'], r['path']): current.objects[r['sha256']] for r in current.entries('inputs')}
    require(('control', 'request.json') in rows and ('source', 'source.zip') in rows,
            'migration_work_inputs_missing', exit_code=6)
    descriptor = parsed(rows['control', 'request.json']); planning = request.command_id == 'migrate.plan'
    _object(descriptor, ('adapter', 'mode', 'backup_sha256', 'source_files_sha256',
                        'planning' if planning else 'bindings'))
    require(descriptor['adapter'] == _ADAPTER and descriptor['mode'] == ('plan' if planning else 'verify'),
            'migration_work_mode_changed', exit_code=6)
    _object(descriptor['planning' if planning else 'bindings'], _PLANNING if planning else _BINDINGS)
    expected = {('control', 'request.json'), ('source', 'source.zip')}
    if not planning:
        expected |= {('plan', 'plan.json'), ('plan', 'report.json')}
        expected |= {key for key in rows if key[0] == 'target'}
        require(any(key[0] == 'target' for key in rows), 'migration_work_target_missing', exit_code=6)
        require(descriptor['backup_sha256'] == descriptor['bindings']['expected_backup_sha256']
            and descriptor['source_files_sha256'] == descriptor['bindings']['expected_source_files_sha256'],
            'migration_work_backup_binding_changed', exit_code=6)
    require(set(rows) == expected, 'migration_work_input_inventory_changed', exit_code=6)
    tasks = current.entries('tasks')
    require([{k: v for k, v in task.items() if k != 'unit_id'} for task in tasks] == _units(),
            'migration_work_phase_plan_changed', exit_code=6)
    done = current.entries('completed')
    require([r['unit_id'] for r in done] == [t['unit_id'] for t in tasks[:len(done)]],
            'migration_work_nonprefix_progress', exit_code=6)
    require(value['state'] in ('running', 'completed'), 'migration_work_not_resumable', exit_code=6)
    return descriptor, rows, tasks, done


def _calculate(current, count, *, gates):
    descriptor, rows, tasks, done = _inputs(current)
    backup_raw = rows['source', 'source.zip']
    backup = verify_source_backup(backup_raw, expected_sha256=descriptor['backup_sha256'],
        expected_source_files_sha256=descriptor['source_files_sha256'])
    require(current.as_dict()['source_bindings'] == {'project_id': backup.manifest['project_id'],
        'scope': ['project'], 'model_root_sha256': backup.manifest['source_model_root_sha256']},
        'migration_work_source_binding_changed', exit_code=6)
    results = [{'backup_sha256': backup.sha256, 'source_files_sha256': descriptor['source_files_sha256'],
                'source_model_root_sha256': backup.manifest['source_model_root_sha256']}]
    plan_raw = report_raw = target = bindings = None
    if count > 1:
        if descriptor['mode'] == 'plan':
            planned = plan_migration(backup.files, **descriptor['planning'])
            require(planned.ready, 'migration_work_plan_incomplete', exit_code=4)
            plan_raw = planned.change_plan.source_bytes; report_raw = planned.canonical_bytes
            target = materialized_files(planned.change_plan, backup.files)
            bindings = {'expected_backup_sha256': backup.sha256,
                'expected_source_files_sha256': descriptor['source_files_sha256'],
                'expected_plan_sha256': planned.change_plan.sha256,
                'expected_inputs_sha256': planned.data['inputs_sha256'],
                'expected_report_sha256': sha256(report_raw).hexdigest(), 'expected_target_version': '0.2.0'}
        else:
            plan_raw, report_raw = rows['plan', 'plan.json'], rows['plan', 'report.json']
            bindings = descriptor['bindings']
            recheck_migration_plan(plan_raw, backup.files, **{key: bindings[key] for key in
                ('expected_plan_sha256', 'expected_inputs_sha256', 'expected_target_version')})
            value = ChangePlan(plan_raw).data
            planned = plan_migration(backup.files, inputs=value['operations'][0]['inputs'],
                **{key: value[key] for key in ('actor','planned_at','change_plan_id','request_id')},
                target_version=bindings['expected_target_version'])
            require(sha256(report_raw).hexdigest() == bindings['expected_report_sha256']
                    and jcs(parsed(report_raw)) == planned.canonical_bytes,
                    'migration_work_report_changed', exit_code=6)
            target = {p: raw for (kind, p), raw in rows.items() if kind == 'target'}
        results.append({'plan_sha256': ChangePlan(plan_raw).sha256,
                        'plan_source_sha256': sha256(plan_raw).hexdigest(), 'report': planned.data})
    if count > 2:
        verification = verify_migration(backup_raw, plan_raw, report_raw, target, gates=gates, **bindings).data
        results.append(verification)
    records = [{'format_version': 'migration-work-phase-v1', 'phase': phase, 'result': result}
               for phase, result in zip(_PHASES[:count], results[:count])]
    for entry, record in zip(done, records):
        require(current.objects[entry['evidence']['sha256']] == jcs(record),
                'migration_work_phase_evidence_changed', exit_code=6)
    return records, (descriptor, backup_raw, plan_raw, report_raw, bindings)


def _outcome(current, records):
    return {'format_version': 'migration-work-result-v1', 'command_id': current.as_dict()['command_id'],
        'target_observation': 'planned_target' if current.as_dict()['command_id'] == 'migrate.plan' else 'provided_target_bytes',
        'planning': records[1]['result']['report'], 'verification': records[2]['result'],
        'project_writes_performed': False, 'write_authorized': False, 'approval_granted': False}


def check_outcome(value, document, exit_code):
    """Closed inert result validation; semantic execution is rechecked by adapters."""
    _object(document, ('format_version', 'command_id', 'target_observation', 'planning',
                       'verification', 'project_writes_performed', 'write_authorized', 'approval_granted'))
    planning = value['command_id'] == 'migrate.plan'
    require(document['format_version'] == 'migration-work-result-v1'
        and document['command_id'] == value['command_id']
        and value['command_class'] == ('plan_output' if planning else 'read_only')
        and document['target_observation'] == ('planned_target' if planning else 'provided_target_bytes')
        and type(exit_code) is int and exit_code == 0
        and all(document[k] is False for k in ('project_writes_performed', 'write_authorized', 'approval_granted'))
        and type(document['planning']) is dict and type(document['verification']) is dict,
        'migration_work_result_invalid', exit_code=6)


def resume_migration_work(store, *, gates=()):
    """Publish at most one new phase under the native checkpoint lease."""
    _initial(store, _runtime_build())
    def advance(current):
        _, _, tasks, done = _inputs(current)
        count = len(done)
        records, _ = _calculate(current, min(count + 1, len(tasks)), gates=gates)
        if current.as_dict()['state'] == 'completed':
            record = read_completion(current.as_dict(), current.objects, current._registry)
            require(record['outcome'] == _outcome(current, records), 'migration_work_result_changed', exit_code=6)
            return current
        if count < len(tasks):
            return partition_work_manifest(current, {tasks[count]['unit_id']: jcs(records[count])})
        return complete_work_manifest(current, _outcome(current, records), exit_code=0)
    return store._update(advance)


def migration_work_result(store, *, gates=()):
    """Fresh native recomputation of a complete retained result, without writes."""
    _initial(store, _runtime_build())
    current = store.read()
    require(current.as_dict()['state'] == 'completed', 'migration_work_incomplete', exit_code=6)
    records, _ = _calculate(current, len(_PHASES), gates=gates)
    actual = _outcome(current, records)
    require(read_completion(current.as_dict(), current.objects, current._registry)['outcome'] == actual,
            'migration_work_result_changed', exit_code=6)
    return actual


def apply_migration_work(store, root, *, transaction_id, backup_path, backup_root, authority, gates=()):
    """One native transaction from fully rechecked planning bytes and fresh host inputs."""
    result = migration_work_result(store, gates=gates)
    require(result['command_id'] == 'migrate.plan', 'migration_work_planning_required', exit_code=6)
    from ..migration.transaction import apply_migration_plan
    plan = ChangePlan(jcs(result['planning']['change_plan']))
    binding = result['verification']['binding']
    current = store.read(); _, rows, _, _ = _inputs(current)
    backup = rows['source', 'source.zip']
    require(sha256(backup).hexdigest() == binding['backup_sha256'], 'migration_work_backup_changed', exit_code=6)
    return apply_migration_plan(root, plan.source_bytes,
        expected_plan_sha256=binding['plan_sha256'], expected_inputs_sha256=binding['inputs_sha256'],
        expected_target_version=binding['target_version'], transaction_id=transaction_id,
        backup_path=backup_path, backup_root=backup_root, backup_sha256=binding['backup_sha256'],
        backup_size=len(backup), backup_source_files_sha256=binding['source_files_sha256'],
        authority=authority, gates=gates)
