"""Durable candidate windows and one complete import-plan target reduction.

This closed read-only embedding adapter consumes the same explicit parsed
artifact candidates as prepare_import_plan. It never parses external bytes,
installs a CLI handler, publishes artifacts or grants approval. Apply must use
the existing import executor with current inputs and live authority; saved
Work evidence, including a completed plan, is not execution truth.
"""
from dataclasses import asdict, dataclass
from hashlib import sha256

from ..changes import ChangePlan
from ..changes.target_values import TargetPolicy
from ..cli.contracts import CommandClass, EffectScope, PreflightProfile
from ..cli.registry import CommandRegistry
from ..cli.requests import CommandRequest
from ..cli.results import CommandResult, FailureKind
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..runtime.controlled import _invocation
from ..work._data_contract import _object, _parse
from ..work._unit_window import UnitWindow
from ..work.checkpoints import CheckpointStore
from ..work.manifest import (WorkManifest, create_work_manifest, read_work_manifest,
                             partition_work_manifest, complete_work_manifest)
from ..work.resume import _compatible_read, _require, _runtime_build
from . import _import_work_inputs as inputs_service
from ._planning_candidates import _CandidateChanges, _prepare_candidate_changes
from .identities import ExternalIdentity, NativeIdentityIndex
from .planning import _finish_import_plan

_REQUEST = CommandRequest('import.plan')
_SCHEMA = 'import-plan-work-v1'
_CHANGE_FIELDS = ('operations', 'objects', 'losses', 'diagnostics', 'conflicts')


def _contract(registry):
    _require(type(registry) is CommandRegistry, 'trusted_import_registry_required')
    command = registry.bind_request(_REQUEST).command
    _require(command.command_class is CommandClass.READ_ONLY
        and command.effect_scope is EffectScope.NONE
        and command.preflight_profile is PreflightProfile.BOOTSTRAP
        and command.protocol is not None and command.protocol.result_schema == _SCHEMA
        and {0, 3, 5} <= set(command.protocol.handler_exit_codes), 'unsupported_import_work_contract')


def _sources(context):
    return {'project_id': context['project_id'], 'scope': ['explicit_saved_model'],
            'model_root_sha256': context['model_root_sha256']}


def prepare_import_work(registry, model, candidates, **options):
    """Capture owned bytes and authoring inputs without mapping or target writes.

    options are prepare_import_plan's inputs except gates: trusted callbacks
    are supplied afresh to advance_import_work, never persisted or discovered.
    """
    _contract(registry)
    context, inputs = inputs_service.capture(model, candidates, **options)
    return create_work_manifest(registry, _REQUEST, tool_build=_runtime_build(),
        source_bindings=_sources(context), inputs=inputs,
        units=inputs_service.declarations(context))


def _checked_plan(current, registry, build):
    _contract(registry)
    _require(type(current) is WorkManifest, 'checked_work_required')
    checked = _compatible_read(read_work_manifest, current.raw, current.objects,
                              registry=registry, expected_tool_build=build)
    context, inputs = inputs_service.saved(checked)
    inputs_service.supplied(context, inputs)
    value = checked.as_dict()
    _require(value['command_id'] == _REQUEST.command_id
        and value['normalized_arguments'] == {'arguments': {}, 'options': {}}
        and value['source_bindings'] == _sources(context)
        and value['state'] in ('running', 'completed'), 'unsupported_import_work_plan')
    _require([{k: t[k] for k in ('key', 'phase', 'range')} for t in checked.entries('tasks')]
             == inputs_service.declarations(context), 'import_work_task_inventory_changed')
    return checked


def _merge(rows):
    return _CandidateChanges(**{name: [item for row in rows for item in row['observation'][name]]
                               for name in _CHANGE_FIELDS})


def _report(report, rows, context, inputs):
    """Check retained data bindings, not authenticity or live write permission."""
    _object(report, ('format_version', 'binding', 'strategy', 'change_plan_id', 'input_sha256',
        'mapping_sha256', 'operations', 'created_ids', 'updated_ids', 'objects', 'skipped',
        'conflicts', 'losses', 'diagnostics', 'attachments', 'attachment_scope',
        'target_model_root_sha256', 'target_assessment', 'change_plan', 'plan_valid', 'exit_code',
        'candidate_origin', 'input_parsed', 'import_completed', 'execution_ready', 'write_authorized'))
    candidates, selected, options = inputs_service.supplied(context, inputs)
    changes = _merge(rows); resource = selected.resource
    plan = ChangePlan(canonical_json_bytes(report['change_plan']))
    _require(type(report['target_assessment']) is dict
             and type(report['target_assessment'].get('binding')) is dict, 'invalid_import_work_report')
    expected = {'input_format': options['input_format'],
        'input_sha256': sha256(options['input_bytes']).hexdigest(), 'input_size': len(options['input_bytes']),
        'mapping': resource.binding(), 'mapping_source_sha256': resource.source_sha256,
        'candidates_sha256': canonical_json_sha256(candidates),
        'base_model_root_sha256': context['model_root_sha256'], 'change_plan_sha256': plan.sha256,
        'target_binding': report['target_assessment']['binding']}
    _require(canonical_json_bytes(report['binding']) == canonical_json_bytes(expected)
        and report['format_version'] == 'artifact-import-plan-v1'
        and report['candidate_origin'] == 'explicit_parsed_artifacts'
        and all(report[flag] is False for flag in
                ('input_parsed', 'import_completed', 'execution_ready', 'write_authorized'))
        and type(report['plan_valid']) is bool
        and type(report['exit_code']) is int and 0 <= report['exit_code'] <= 7
        and report['plan_valid'] is (report['exit_code'] == 0), 'invalid_import_work_report')
    _require(all(canonical_json_bytes(report[name]) == canonical_json_bytes(getattr(changes, name))
                 for name in ('operations', 'objects', 'conflicts', 'losses'))
        and canonical_json_bytes(plan.data['operations']) == canonical_json_bytes(changes.operations),
        'import_work_candidate_results_changed')
    target = report['target_assessment']; target_binding = target['binding']; data = plan.data
    _require(all(target.get(flag) is False for flag in ('project_files_verified', 'atomic_snapshot',
        'transaction_prepared', 'execution_ready', 'approval_granted', 'write_authorized'))
        and type(target.get('target_validated')) is bool
        and type(target.get('validation')) is dict
        and type(target['validation'].get('diagnostics')) is list
        and type(target['validation'].get('exit_code')) is int
        and 0 <= target['validation']['exit_code'] <= 7, 'invalid_import_work_target')
    bound = {'strategy': options['strategy'], 'change_plan_id': options['change_plan_id'],
        'input_sha256': expected['input_sha256'], 'mapping_sha256': resource.sha256,
        'created_ids': sorted(o['result_id'] for o in changes.operations if o['op'] == 'create'),
        'updated_ids': sorted(o['target'] for o in changes.operations if o['op'] == 'update'),
        'skipped': [o for o in changes.objects if o['action'] == 'skip'],
        'diagnostics': changes.diagnostics + target['validation']['diagnostics'],
        'attachment_scope': 'complete_supplied_target',
        'attachments': target['target_manifest']['attachments'],
        'target_model_root_sha256': data['expected_result']['model_root_sha256']}
    _require(all(canonical_json_bytes(report[k]) == canonical_json_bytes(v) for k, v in bound.items())
        and all(canonical_json_bytes(data[k]) == canonical_json_bytes(options[k]) for k in
                ('change_plan_id', 'request_id', 'actor', 'planned_at', 'metadata_policy_version'))
        and target_binding['command'] == context['policy']
        and target_binding['strict'] is options['strict']
        and target_binding['plan_sha256'] == plan.sha256
        and target_binding['base_model_root'] == expected['base_model_root_sha256']
        and target_binding['target_model_root'] == bound['target_model_root_sha256'],
        'import_work_target_binding_changed')
    valid = target['target_validated'] and not changes.losses and not changes.conflicts and not any(
        d.get('exit_code', 0) for d in bound['diagnostics'])
    _require(report['plan_valid'] is bool(valid)
        and report['exit_code'] == (0 if valid else max(3, target['validation']['exit_code'])),
        'import_work_target_result_changed')


def _records(current):
    tasks, completed = current.entries('tasks'), current.entries('completed')
    _require([r['unit_id'] for r in completed] == [t['unit_id'] for t in tasks[:len(completed)]],
             'import_work_completion_must_be_prefix')
    context, inputs = inputs_service.saved(current)
    candidates, _, _ = inputs_service.supplied(context, inputs)
    native = NativeIdentityIndex([SourceRelations(inputs['project', p], path=p) for p in context['documents']])
    rows, keys, owners = [], set(), set(); value = current.as_dict()
    for item, task in zip(completed, tasks):
        raw = current.objects[item['evidence']['sha256']]; row = _parse(raw)
        _object(row, ('format_version', 'unit_id', 'input_manifest_sha256',
                      'task_manifest_sha256', 'phase', 'observation'))
        _require(canonical_json_bytes(row) == raw and row['format_version'] == 'import-work-unit-v1'
            and row['unit_id'] == task['unit_id'] and row['phase'] == task['phase']
            and row['input_manifest_sha256'] == value['input_manifest_sha256']
            and row['task_manifest_sha256'] == value['task_manifest_sha256'], 'invalid_import_work_completion')
        if row['phase'] == 'import_candidates':
            n = task['range']['candidate_index']; candidate = candidates[n]; data = row['observation']
            _object(data, _CHANGE_FIELDS)
            _require(all(type(data[k]) is list and all(type(v) is dict for v in data[k])
                         for k in _CHANGE_FIELDS) and len(data['objects']) == 1, 'invalid_import_work_candidate')
            observed = data['objects'][0]
            _object(observed, ('candidate_index', 'artifact_id', 'identity', 'comparison', 'action'))
            _object(candidate, ('identity', 'external_type', 'fields', 'new_artifact'))
            identity = ExternalIdentity(candidate['identity']); owner = native.lookup('artifact', *identity.key)
            _require(owner is not None or (type(candidate['new_artifact']) is dict
                     and type(candidate['new_artifact'].get('id')) is str), 'invalid_import_work_candidate')
            native_id = candidate['new_artifact']['id'] if owner is None else owner['artifact_id']
            _require(type(observed['candidate_index']) is int and observed['candidate_index'] == n
                and observed['identity'] == identity.data and observed['artifact_id'] == native_id
                and identity.key not in keys and native_id not in owners, 'import_work_candidate_binding_changed')
            keys.add(identity.key); owners.add(native_id)
        else:
            _report(row['observation'], rows, context, inputs)
        rows.append(row)
    return rows


def _outcome(current):
    _require(not current.entries('remaining'), 'unfinished_import_work_cannot_complete')
    rows = _records(current); value = current.as_dict(); report = rows[-1]['observation']
    result = {'format_version': _SCHEMA, 'input_manifest_sha256': value['input_manifest_sha256'],
        'task_manifest_sha256': value['task_manifest_sha256'], 'source_scope': 'explicit_saved_model',
        'project_files_verified': False, 'import_plan': report,
        'import_completed': False, 'write_authorized': False}
    return (CommandResult(_REQUEST.command_id, result=result) if report['exit_code'] == 0 else
            CommandResult.failed(_REQUEST.command_id, FailureKind(report['exit_code']), complete=True, result=result))


def _checked_final(current, registry):
    if current.as_dict()['state'] == 'completed':
        from ..work._completion import read_completion
        saved = read_completion(current.as_dict(), current.objects, registry)
        outcome = _outcome(current)
        _require(saved['exit_code'] == outcome.exit_code and canonical_json_bytes(saved['outcome'])
                 == canonical_json_bytes(outcome.as_dict()), 'import_work_final_result_changed')


def _checked_store(store, registry, build):
    _require(type(store) is CheckpointStore, 'trusted_work_store_required')
    initial = _compatible_read(_checked_plan, store._initial, registry, build)
    _require(initial.as_dict()['checkpoint_generation'] == 0 and not initial.entries('completed'), 'initial_work_required')
    current = _compatible_read(store.read)
    _require(current is not None, 'published_work_required')
    current = _compatible_read(_checked_plan, current, registry, build)
    _compatible_read(_records, current); _compatible_read(_checked_final, current, registry)
    return current


@dataclass(frozen=True)
class ImportWorkStep:
    manifest: WorkManifest
    executed_unit_ids: tuple
    reused_unit_ids: tuple
    outcome_bytes: bytes | None = None
    command_exit_code: int | None = None


def advance_import_work(store, call, *, registry, policy, gates=(), max_units=1):
    """Execute a nonempty prefix of candidate units or the final whole target.

    Completed mapping/comparison kernels are not executed on resume. Each
    candidate and the reserved target reduction are still memory-resident.
    All target gates are fresh trusted host inputs; no approval is stored.
    """
    _invocation(call)
    _require(type(max_units) is int and max_units > 0, 'invalid_import_work_window')
    _require(type(policy) is TargetPolicy, 'import_work_policy_required')
    build = _runtime_build(); current = _checked_store(store, registry, build)
    context, _ = inputs_service.saved(current)
    _require(policy.data() == context['policy'], 'import_work_policy_changed')
    window = UnitWindow(call); reused = []

    def advance(previous):
        current = _checked_plan(previous, registry, _runtime_build()); _checked_final(current, registry)
        rows = _records(current); reused.extend(r['unit_id'] for r in rows)
        if not current.entries('remaining'): return previous
        context, inputs = inputs_service.saved(current)
        model = inputs_service.restore(context, inputs, store._location)
        candidates, selected, options = inputs_service.supplied(context, inputs)

        def evaluate(task):
            changes = _merge(rows)
            if task['phase'] == 'import_candidates':
                n = task['range']['candidate_index']
                observation = asdict(_prepare_candidate_changes(model, [candidates[n]], selected,
                    strategy=options['strategy'], input_bytes=options['input_bytes'],
                    planned_at=options['planned_at'], start_index=n, prior_objects=changes.objects))
            else:
                reduced = {k: v for k, v in options.items() if k not in ('mapping_key', 'mapping_sha256')}
                observation = _finish_import_plan(model, candidates, selected, changes,
                    policy=policy, gates=gates, **reduced).data
            value = current.as_dict()
            row = {'format_version': 'import-work-unit-v1', 'unit_id': task['unit_id'],
                'input_manifest_sha256': value['input_manifest_sha256'],
                'task_manifest_sha256': value['task_manifest_sha256'],
                'phase': task['phase'], 'observation': observation}
            rows.append(row)
            return row

        additions = window.collect(current.entries('remaining')[:max_units], evaluate)
        _require(_runtime_build() == build, 'runtime_build_changed')
        candidate = partition_work_manifest(current, additions); _records(candidate)
        return candidate

    confirmed = window.update(store, advance)
    _require(_runtime_build() == build, 'runtime_build_changed')
    return ImportWorkStep(confirmed, tuple(window.executed_unit_ids), tuple(reused))


def finalize_import_work(store, *, registry):
    """Complete only the planning result. It is never an import receipt."""
    build = _runtime_build(); current = _checked_store(store, registry, build)
    _outcome(current)
    saved = {}

    def finish(previous):
        current = _checked_plan(previous, registry, _runtime_build()); _checked_final(current, registry)
        outcome = _outcome(current); saved['outcome'] = outcome
        _require(_runtime_build() == build, 'runtime_build_changed')
        return previous if current.as_dict()['state'] == 'completed' else complete_work_manifest(
            current, outcome.as_dict(), exit_code=outcome.exit_code)

    confirmed = _compatible_read(store._update, finish)
    _require(_runtime_build() == build, 'runtime_build_changed')
    outcome = saved['outcome']
    return ImportWorkStep(confirmed, (), tuple(r['unit_id'] for r in _records(confirmed)),
                          canonical_json_bytes(outcome.as_dict()), outcome.exit_code)
