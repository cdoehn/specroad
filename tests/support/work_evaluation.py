"""Shared native model/SRX/Work fixtures and exact direct parity oracle.

The recorded-build sampler is a labelled in-process fixture. PORTABLE is trusted
host code for actual independently built distributions, never stored Work code.
"""

import json

from specroad.cli.contracts import (CommandClass, CommandSpec, CommandProtocol,
                                    EffectScope, PreflightProfile)
from specroad.cli.registry import CommandRegistry
from specroad.diagnostics import known_codes
from specroad.graph.relations import SourceRelations
from specroad.model.canonical import canonical_json_bytes
from specroad.profiles.composition import compose_profiles
from specroad.profiles.values import ProfileResource
from specroad.runtime.consumption import WorkConsumption
from specroad.security import ProjectBoundary
from specroad.srx import EvaluationContext, LoadedGraph, SrxProgram, evaluate
from specroad.srx.types import MISSING
from specroad.validation import ModelDocument, validate_model
from specroad.validation.diagnostics import assess_validation
from specroad.work.checkpoints import CheckpointStore
from specroad.work.evaluation import (prepare_evaluation_work, advance_evaluation_work,
                                      finalize_evaluation_work)
from specroad.work.manifest import partition_work_manifest
from specroad.work.root import WorkDirectory
from specroad.work.snapshot import InputSnapshotTask
from support.artifacts import artifact_bytes
from support.model_validation import artifact, edge
from support.profiles import profile_data
from support.read_only import inventory, no_write_attempts
from support.srx import expression_document, roots, literal, field
from support.srx_graph import reach, count
from test_work_progress import unknown


def registry():
    def unused(invocation):
        raise AssertionError('The trusted host registry is a data binding, not stored execution code')
    return CommandRegistry((CommandSpec('analysis.evaluate', ('analysis', 'evaluate'),
        CommandClass.READ_ONLY, PreflightProfile.BOOTSTRAP, EffectScope.NONE, unused,
        protocol=CommandProtocol('work-evaluation-v1', {'command_id': 'analysis.evaluate'},
            handler_exit_codes=(0, 1), diagnostic_codes=(*known_codes(), 'MODEL_VALIDATION', 'VALIDATION_UNAVAILABLE'))),))


def data():
    values = [artifact(number=i) for i in range(1, 5)]
    values[0]['relations'] = [edge(values[1], number=1)]
    values[1]['relations'] = [edge(values[2], number=2)]
    inputs = [{'root_id': 'model', 'path': v['id'] + '.json', 'raw': artifact_bytes(v)} for v in values]
    inputs.append({'root_id': 'profiles', 'path': 'core.json', 'raw': artifact_bytes(profile_data(profile_id='core'))})
    jobs = [{'key': 'closure', 'kind': 'validate', 'core_profile': 'core@0.2.0', 'selected_ids': [values[2]['id']]}]
    expressions = [reach(values[2]['id'], depth=2, types=['supersedes']), count(types=['supersedes']), field('/not_present'), literal(False)]
    for index, node in enumerate(expressions):
        jobs.append({'key': 'srx-' + str(index), 'kind': 'srx', 'rule_id': 'parity-' + str(index),
                     'program': expression_document(node), 'context': roots(values[0])})
    return inputs, jobs, values


def setup(tmp_path, *, input_data=None, job_data=None, publish=True):
    inputs, jobs, values = data()
    if input_data is not None: inputs = input_data
    if job_data is not None: jobs = job_data
    project = tmp_path / 'project'; project.mkdir(parents=True)
    for item in inputs:
        p = project / item['root_id'] / item['path']; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(item['raw'])
    boundaries = {key: ProjectBoundary(project / key) for key in ('model', 'profiles')}
    with InputSnapshotTask(boundaries, [{k: i[k] for k in ('root_id', 'path')} for i in inputs]) as capture:
        while not capture.state['complete']:
            capture.advance(3)
        captured = capture.work_inputs()
    before = inventory(tmp_path)
    with no_write_attempts():
        initial = prepare_evaluation_work(registry(), inputs=captured, jobs=jobs)
    assert inventory(tmp_path) == before
    location = WorkDirectory(initial, protected_roots=tuple(boundaries.values()), directory=tmp_path / 'work')
    store = CheckpointStore(location, initial)
    if publish: store.publish(initial)
    return inputs, jobs, values, project, boundaries, initial, location, store


def advance(store, *, size=1, profile='constrained', sampler=unknown, options=None):
    call = WorkConsumption(sampler=sampler).begin({'--resource-profile': profile, **(options or {})})
    try:
        result = advance_evaluation_work(store, call, registry=registry(), max_units=size)
    finally:
        measurement = call.finish()
    return result, measurement


def direct(inputs, jobs):
    documents = tuple(ModelDocument(i['path'], i['raw']) for i in inputs if i['root_id'] == 'model')
    profiles = tuple(ProfileResource(i['raw']) for i in inputs if i['root_id'] == 'profiles')
    results = []
    for job in jobs:
        if job['kind'] == 'validate':
            report = validate_model(documents, profile=compose_profiles(profiles, core_key=job['core_profile']), selected_ids=job['selected_ids'])
            assessment = assess_validation(report, documents=documents)
            result, code = assessment.as_dict(), assessment.exit_code
        else:
            graph = LoadedGraph(tuple(SourceRelations(d.content, path=d.path) for d in documents), rule_id=job['rule_id'])
            value = evaluate(SrxProgram(job['program'], rule_id=job['rule_id']), EvaluationContext(job['context'], rule_id=job['rule_id'], graph=graph))
            result = {'value_state': 'missing' if value is MISSING else 'value', 'value': None if value is MISSING else value}; code = 0
        results.append({'key': job['key'], 'kind': job['kind'], 'observation': result, 'exit_code': code})
    return results


PORTABLE = r'''
import json,sys
from pathlib import Path
from specroad.cli.contracts import CommandClass,CommandSpec,CommandProtocol,EffectScope,PreflightProfile
from specroad.cli.registry import CommandRegistry
from specroad.diagnostics import known_codes
from specroad.runtime.consumption import WorkConsumption
from specroad.security import ProjectBoundary
from specroad.work.checkpoints import CheckpointStore
from specroad.work.evaluation import prepare_evaluation_work,advance_evaluation_work,finalize_evaluation_work
from specroad.work.manifest import read_work_manifest
from specroad.work.resume import _runtime_build
from specroad.work.root import WorkDirectory
def unused(invocation):raise AssertionError('No stored handler execution')
registry=CommandRegistry((CommandSpec('analysis.evaluate',('analysis','evaluate'),CommandClass.READ_ONLY,
    PreflightProfile.BOOTSTRAP,EffectScope.NONE,unused,protocol=CommandProtocol('work-evaluation-v1',
    {'command_id':'analysis.evaluate'},handler_exit_codes=(0,1),
    diagnostic_codes=(*known_codes(),'MODEL_VALIDATION','VALIDATION_UNAVAILABLE'))),))
packet,work,project,action,profile=sys.argv[1:]
packet=Path(packet);data=json.loads(packet.read_text())
if action=='plan':
    inputs=[{**i,'raw':bytes.fromhex(i['raw'])} for i in data['inputs']]
    initial=prepare_evaluation_work(registry,inputs=inputs,jobs=data['jobs'])
    data['initial']=initial.raw.hex();data['objects']={k:v.hex() for k,v in initial.objects.items()}
    packet.write_text(json.dumps(data))
else:
    initial=read_work_manifest(bytes.fromhex(data['initial']),{k:bytes.fromhex(v) for k,v in data['objects'].items()},
                              registry=registry,expected_tool_build=_runtime_build())
location=WorkDirectory(initial,protected_roots=tuple(ProjectBoundary(Path(project)/k) for k in ('model','profiles')),directory=work)
store=CheckpointStore(location,initial)
if action=='plan':
    store.publish(initial); print(json.dumps({'generation':0}))
elif action=='advance':
    call=WorkConsumption().begin({'--resource-profile':profile,'--step-cpu-ms':1})
    try:step=advance_evaluation_work(store,call,registry=registry,max_units=1)
    finally:call.finish()
    print(json.dumps({'generation':step.manifest.as_dict()['checkpoint_generation'],'executed':list(step.executed_unit_ids)}))
else:
    result=finalize_evaluation_work(store,registry=registry)
    print(json.dumps({'outcome':json.loads(result.outcome_bytes),'generation':result.manifest.as_dict()['checkpoint_generation']}))
'''


def failed_inputs():
    inputs, jobs, values = data()
    inputs[-1]['raw'] = artifact_bytes(profile_data(profile_id='core', forbidden_fields=[
        {'artifact_types': ['goal'], 'maturities': [], 'fields': ['/statement']}]))
    return inputs, jobs, values


def run(store, operation):
    return advance(store) if operation == 'advance' else finalize_evaluation_work(store, registry=registry())


def copy_record(tmp_path, setup_values, mutate):
    _, _, _, _, boundaries, initial, _, actual = setup_values
    step, _ = advance(actual); item = step.manifest.entries('completed')[0]
    row = json.loads(step.manifest.objects[item['evidence']['sha256']]); mutate(row)
    candidate = partition_work_manifest(initial, {item['unit_id']: canonical_json_bytes(row)})
    location = WorkDirectory(initial, protected_roots=tuple(boundaries.values()), directory=tmp_path / 'untrusted-work')
    store = CheckpointStore(location, initial); store.publish(initial); store.publish(candidate)
    return store, candidate
