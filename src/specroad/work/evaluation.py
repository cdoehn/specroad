"""Closed host adapter for durable evaluations of explicitly saved model bytes.

The trusted caller supplies a registered analysis.evaluate contract and an
independent initial binding. No handler, Python object or source locator is
restored from work data. Complete native evaluations are the current units;
large within-evaluation cursors and a public CLI remain separate integrations.
"""

from dataclasses import dataclass

from ..cli.contracts import CommandClass, EffectScope, PreflightProfile
from ..cli.registry import CommandRegistry
from ..cli.requests import CommandRequest
from ..cli.results import CommandResult, FailureKind
from ..diagnostics import Diagnostic
from ..result_contract import ResultContractError
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..runtime.controlled import _invocation, evaluate_srx, load_srx_graph
from ._data_contract import WorkManifestError, _copy, _object, _parse, _text
from ._unit_window import UnitWindow
from .checkpoints import CheckpointStore, CheckpointStorageError
from .manifest import (WorkManifest, create_work_manifest, read_work_manifest,
                       partition_work_manifest, complete_work_manifest)
from .resume import WorkResumeError, _compatible_read, _require, _runtime_build


_REQUEST = CommandRequest('analysis.evaluate')
_SOURCES = {'project_id': None, 'scope': ['explicit_saved_model'], 'model_root_sha256': None}
_SCHEMA = 'work-evaluation-v1'


class WorkEvaluationDataError(WorkResumeError):
    """A concrete missing/changed stored resource, never a source fallback."""

    def __init__(self, reason, *, resource):
        super().__init__(reason)
        self._resource = canonical_json_bytes(resource)

    def as_dict(self):
        return {**super().as_dict(), 'resource': _parse(self._resource)}


def _stored(reader, initial, *args):
    try:
        return _compatible_read(reader, *args)
    except (CheckpointStorageError, FileNotFoundError) as error:
        path = error.path if isinstance(error, CheckpointStorageError) else error.filename
        name = path.rsplit('/', 1)[-1] if type(path) is str else None
        row = next((row for row in initial.entries('inputs') if row['sha256'] == name), None)
        resource = ({k: row[k] for k in ('root_id', 'path', 'sha256')} if row else
                    {'root_id': 'work', 'path': path if type(path) is str and not path.startswith('/') else None})
        raise WorkEvaluationDataError('evaluation_work_data_unavailable', resource=resource) from error


class WorkEvaluationBlocked(WorkResumeError):
    """Retain every native finding when a required model check is incomplete."""

    def __init__(self, assessment):
        super().__init__('evaluation_checks_incomplete', exit_code=assessment.exit_code)
        self.observation_bytes = canonical_json_bytes(assessment.as_dict())

    def as_dict(self):
        return {**super().as_dict(), 'observation': _parse(self.observation_bytes)}


def _contract(registry):
    _require(type(registry) is CommandRegistry, 'trusted_evaluation_registry_required')
    command = registry.bind_request(_REQUEST).command
    _require(command.command_class is CommandClass.READ_ONLY
             and command.effect_scope is EffectScope.NONE
             and command.preflight_profile is PreflightProfile.BOOTSTRAP
             and command.protocol is not None
             and command.protocol.result_schema == _SCHEMA
             and {0, 1} <= set(command.protocol.handler_exit_codes),
             'unsupported_evaluation_contract')


def _jobs(jobs):
    data = _copy({'jobs': jobs})['jobs']
    _require(type(data) is list and bool(data), 'evaluation_jobs_required')
    seen = set()
    for job in data:
        _require(type(job) is dict and type(job.get('kind')) is str,
                 'invalid_evaluation_job')
        if job['kind'] == 'validate':
            _object(job, ('key', 'kind', 'core_profile', 'selected_ids'))
            _text(job['core_profile'])
            selected = job['selected_ids']
            _require(selected is None or (type(selected) is list and bool(selected)
                and all(type(i) is str and bool(i) for i in selected)
                and len(selected) == len(set(selected))), 'invalid_evaluation_selection')
            if selected is not None:
                job['selected_ids'] = sorted(selected)
        elif job['kind'] == 'srx':
            _object(job, ('key', 'kind', 'rule_id', 'program', 'context'))
            _text(job['rule_id'])
            _require(type(job['program']) is dict and type(job['context']) is dict,
                     'invalid_evaluation_srx_data')
        else:
            raise WorkResumeError('unsupported_evaluation_kind')
        _text(job['key'])
        _require(job['key'] not in seen, 'duplicate_evaluation_key')
        seen.add(job['key'])
    return data


def prepare_evaluation_work(registry, *, inputs, jobs):
    """Bind a finite explicit input set and complete native evaluation units."""
    _contract(registry)
    jobs = _jobs(jobs)
    initial = create_work_manifest(registry, _REQUEST, tool_build=_runtime_build(),
        source_bindings=_SOURCES, inputs=inputs,
        units=[{'key': j['key'], 'phase': 'evaluate', 'range': j} for j in jobs])
    _require(all(row['root_id'] in ('model', 'profiles') for row in initial.entries('inputs')),
             'unsupported_evaluation_input_root')
    return initial


def _checked_plan(current, registry, build):
    _contract(registry)
    _require(type(current) is WorkManifest, 'checked_work_required')
    checked = _compatible_read(read_work_manifest, current.raw, current.objects,
        registry=registry, expected_tool_build=build)
    value = checked.as_dict()
    _require(value['command_id'] == _REQUEST.command_id
             and value['normalized_arguments'] == {'arguments': {}, 'options': {}}
             and value['source_bindings'] == _SOURCES
             and value['state'] in ('running', 'completed'), 'unsupported_evaluation_plan')
    tasks = checked.entries('tasks')
    jobs = _jobs([task['range'] for task in tasks])
    _require(all(task['key'] == job['key'] and task['phase'] == 'evaluate'
                 and canonical_json_bytes(task['range']) == canonical_json_bytes(job)
                 for task, job in zip(tasks, jobs)), 'unsupported_evaluation_plan')
    _require(all(row['root_id'] in ('model', 'profiles') for row in checked.entries('inputs')),
             'unsupported_evaluation_input_root')
    return checked


def _records(current):
    try:
        return _read_records(current)
    except (WorkManifestError, ModelError, ResultContractError) as error:
        raise WorkResumeError('invalid_evaluation_completion') from error


def _read_records(current):
    """Read retained evidence without rerunning completed model/SRX work."""
    tasks = {t['unit_id']: t for t in current.entries('tasks')}
    value = current.as_dict(); records = []
    for item in current.entries('completed'):
        raw = current.objects[item['evidence']['sha256']]; row = _parse(raw)
        _object(row, ('format_version', 'unit_id', 'key', 'kind', 'input_manifest_sha256',
                      'task_manifest_sha256', 'observation', 'exit_code', 'diagnostics'))
        task = tasks[item['unit_id']]
        _require(canonical_json_bytes(row) == raw
            and row['format_version'] == 'work-evaluation-unit-v1'
            and row['unit_id'] == item['unit_id'] and row['key'] == task['key']
            and row['kind'] == task['range']['kind']
            and row['input_manifest_sha256'] == value['input_manifest_sha256']
            and row['task_manifest_sha256'] == value['task_manifest_sha256']
            and type(row['exit_code']) is int and row['exit_code'] in (0, 1)
            and type(row['diagnostics']) is list and type(row['observation']) is dict,
            'invalid_evaluation_completion')
        for diagnostic in row['diagnostics']:
            Diagnostic.from_dict(diagnostic)
        if row['kind'] == 'srx':
            observation = row['observation']; _object(observation, ('value_state', 'value'))
            _require(observation['value_state'] in ('value', 'missing')
                and (observation['value_state'] != 'missing' or observation['value'] is None)
                and row['exit_code'] == 0 and row['diagnostics'] == [],
                'invalid_evaluation_completion')
        else:
            observation = row['observation']
            _require(observation.get('checks_complete') is True
                and type(observation.get('exit_code')) is int
                and observation['exit_code'] == row['exit_code']
                and observation.get('status') == ('success' if row['exit_code'] == 0 else 'failed')
                and canonical_json_bytes(observation.get('diagnostics')) == canonical_json_bytes(row['diagnostics']),
                'invalid_evaluation_completion')
            from ._evaluation_evidence import check_validation_observation
            check_validation_observation(current, task, observation)
        records.append(row)
    return records


def _evaluate(current, task, call):
    from ..graph.relations import SourceRelations
    from ..profiles.values import ProfileResource
    from ..profiles.composition import compose_profiles
    from ..srx import EvaluationContext, SrxProgram
    from ..srx.types import MISSING
    from ..validation import ModelDocument, validate_model
    from ..validation.diagnostics import assess_validation
    inputs = current.entries('inputs'); job = task['range']
    documents = tuple(ModelDocument(row['path'], current.objects[row['sha256']])
                      for row in inputs if row['root_id'] == 'model')
    if job['kind'] == 'validate':
        profiles = tuple(ProfileResource(current.objects[row['sha256']])
                         for row in inputs if row['root_id'] == 'profiles')
        profile = compose_profiles(profiles, core_key=job['core_profile'])
        report = validate_model(documents, profile=profile, selected_ids=job['selected_ids'])
        assessment = assess_validation(report, documents=documents)
        if not report.complete:
            raise WorkEvaluationBlocked(assessment)
        observation = assessment.as_dict(); code = assessment.exit_code
        diagnostics = [d.as_dict() for d in assessment.diagnostics]
    else:
        sources = tuple(SourceRelations(d.content, path=d.path) for d in documents)
        graph = load_srx_graph(sources, call, rule_id=job['rule_id'])
        context = EvaluationContext(job['context'], rule_id=job['rule_id'], graph=graph,
                                    resource_options={'--resource-profile': call._policy['profile']})
        result = evaluate_srx(SrxProgram(job['program'], rule_id=job['rule_id']), context, call)
        observation = {'value_state': 'missing' if result.value is MISSING else 'value',
                       'value': None if result.value is MISSING else result.value}
        code, diagnostics = 0, []
    value = current.as_dict()
    return {'format_version': 'work-evaluation-unit-v1', 'unit_id': task['unit_id'],
        'key': task['key'], 'kind': job['kind'],
        'input_manifest_sha256': value['input_manifest_sha256'],
        'task_manifest_sha256': value['task_manifest_sha256'],
        'observation': observation, 'exit_code': code, 'diagnostics': diagnostics}


def _outcome(current):
    rows = _records(current)
    _require(not current.entries('remaining'), 'unfinished_evaluation_cannot_complete')
    value = current.as_dict()
    result = {'format_version': _SCHEMA, 'input_manifest_sha256': value['input_manifest_sha256'],
        'task_manifest_sha256': value['task_manifest_sha256'],
        'source_scope': 'explicit_saved_model', 'project_files_verified': False,
        'results': [{k: row[k] for k in ('key', 'kind', 'observation', 'exit_code')} for row in rows]}
    diagnostics = tuple(Diagnostic.from_dict(d) for row in rows for d in row['diagnostics'])
    if any(row['exit_code'] for row in rows):
        return CommandResult.failed(_REQUEST.command_id, FailureKind.POLICY,
                                    complete=True, result=result, diagnostics=diagnostics)
    return CommandResult(_REQUEST.command_id, result=result, diagnostics=diagnostics)


def _checked_final(current, registry):
    if current.as_dict()['state'] == 'completed':
        from ._completion import read_completion
        saved = read_completion(current.as_dict(), current.objects, registry)
        actual = _outcome(current)
        _require(canonical_json_bytes(saved['outcome']) == canonical_json_bytes(actual.as_dict())
                 and saved['exit_code'] == actual.exit_code, 'evaluation_final_result_changed')


def _checked_store(store, registry, build):
    _require(type(store) is CheckpointStore, 'trusted_work_store_required')
    initial = _checked_plan(store._initial, registry, build)
    _require(initial.as_dict()['checkpoint_generation'] == 0 and not initial.entries('completed'),
             'initial_work_required')
    current = _stored(store.read, initial)
    _require(current is not None, 'published_work_required')
    current = _checked_plan(current, registry, build); _records(current)
    _checked_final(current, registry)
    return current


@dataclass(frozen=True)
class EvaluationWorkStep:
    manifest: WorkManifest
    executed_unit_ids: tuple
    reused_unit_ids: tuple
    outcome_bytes: bytes | None = None
    command_exit_code: int | None = None


def advance_evaluation_work(store, call, *, registry, max_units=1):
    """Persist whole evaluations; an exceeded soft window still attempts one."""
    _invocation(call)
    _require(type(max_units) is int and max_units > 0, 'invalid_evaluation_window')
    build = _runtime_build(); _checked_store(store, registry, build)
    window = UnitWindow(call); reused = []

    def advance(previous):
        current = _checked_plan(previous, registry, _runtime_build())
        _checked_final(current, registry)
        rows = _records(current); reused.extend(row['unit_id'] for row in rows)
        additions = window.collect(current.entries('remaining')[:max_units],
                                   lambda task: _evaluate(current, task, call))
        _require(_runtime_build() == build, 'runtime_build_changed')
        if not additions:
            return previous
        candidate = partition_work_manifest(current, additions)
        _records(candidate)
        return candidate

    confirmed = window.update(store, advance)
    _require(_runtime_build() == build, 'runtime_build_changed')
    return EvaluationWorkStep(confirmed, tuple(window.executed_unit_ids), tuple(reused))


def finalize_evaluation_work(store, *, registry):
    """Reduce every saved result and diagnostic in a separate durable state."""
    build = _runtime_build(); current = _checked_store(store, registry, build)
    _outcome(current)  # Refuse unfinished work before a writing lease.
    saved = {}

    def finish(previous):
        current = _checked_plan(previous, registry, _runtime_build())
        _checked_final(current, registry)
        outcome = _outcome(current); saved['outcome'] = outcome
        _require(_runtime_build() == build, 'runtime_build_changed')
        return previous if current.as_dict()['state'] == 'completed' else complete_work_manifest(
            current, outcome.as_dict(), exit_code=outcome.exit_code)

    confirmed = _compatible_read(store._update, finish)
    _require(_runtime_build() == build, 'runtime_build_changed')
    outcome = saved['outcome']
    return EvaluationWorkStep(confirmed, (), tuple(row['unit_id'] for row in _records(confirmed)),
                              canonical_json_bytes(outcome.as_dict()), outcome.exit_code)
