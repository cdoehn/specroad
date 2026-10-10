"""Actual model/graph/SRX results survive durable windows and fresh processes."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from specroad import _build
from specroad.cli.contracts import (CommandClass, CommandSpec, CommandProtocol,
                                    EffectScope, PreflightProfile)
from specroad.cli.registry import CommandRegistry
from specroad.diagnostics import known_codes
from specroad.graph.relations import SourceRelations
from specroad.profiles.composition import compose_profiles
from specroad.profiles.values import ProfileResource
from specroad.runtime.consumption import WorkConsumption
from specroad.security import ProjectBoundary
from specroad.srx import EvaluationContext, LoadedGraph, SrxProgram, evaluate
from specroad.srx.errors import SrxError
from specroad.srx.types import MISSING
from specroad.validation import ModelDocument, validate_model
from specroad.validation.diagnostics import assess_validation
from specroad.work.checkpoints import CheckpointStore
from specroad.work.evaluation import (prepare_evaluation_work, advance_evaluation_work,
    finalize_evaluation_work, WorkEvaluationBlocked)
from specroad.work.resume import WorkResumeError
from specroad.work.root import WorkDirectory
from specroad.work.snapshot import InputSnapshotTask
from support.artifacts import artifact_bytes
from support.model_validation import artifact, edge
from support.profiles import profile_data
from support.read_only import inventory, no_write_attempts
from support.srx import expression_document, roots, literal, field
from support.srx_graph import reach, count
from test_work_progress import ticking, unknown
from test_work_resume import recorded


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


@pytest.mark.parametrize('size', [1, 2, 100])
@pytest.mark.parametrize('profile', ['constrained', 'standard'])
def test_direct_native_results_equal_completed_durable_windows(recorded, tmp_path, size, profile):
    inputs, jobs, values, project, _, initial, _, store = setup(tmp_path)
    before = inventory(project); previous = initial; executed = []
    while store.read().entries('remaining'):
        step, _ = advance(store, size=size, profile=profile)
        assert step.executed_unit_ids and step.manifest.as_dict()['checkpoint_generation'] == previous.as_dict()['checkpoint_generation'] + 1
        assert not set(step.executed_unit_ids).intersection(executed)
        executed.extend(step.executed_unit_ids); previous = step.manifest
    result = finalize_evaluation_work(store, registry=registry())
    document = json.loads(result.outcome_bytes); report = document['result']
    assert result.command_exit_code == 0 and document['summary']['complete'] is True
    assert report['results'] == direct(inputs, jobs)
    assert report['results'][0]['observation']['source_report']['checked_ids'] == sorted(v['id'] for v in values[:3])
    assert report['results'][0]['observation']['source_report']['source_count'] == 4
    assert report['project_files_verified'] is False and report['source_scope'] == 'explicit_saved_model'
    assert report['results'][1]['observation']['value'] is True
    assert report['results'][-1]['observation'] == {'value_state': 'value', 'value': False}
    assert report['results'][-2]['observation'] == {'value_state': 'missing', 'value': None}
    assert len(executed) == len(jobs) and result.manifest.as_dict()['state'] == 'completed'
    assert result.manifest.as_dict()['checkpoint_generation'] == previous.as_dict()['checkpoint_generation'] + 1
    assert inventory(project) == before


@pytest.mark.parametrize('cache', ['absent', 'empty', 'corrupt'])
def test_saved_inputs_survive_source_loss_and_cache_state_without_rerunning_prefix(recorded, tmp_path, monkeypatch, cache):
    inputs, jobs, _, project, _, _, _, store = setup(tmp_path)
    first, _ = advance(store)
    for item in inputs: (project / item['root_id'] / item['path']).unlink()
    if cache != 'absent':
        directory = project / 'model' / '.specroad/cache'; directory.mkdir(parents=True)
        if cache == 'corrupt': (directory / 'untrusted').write_bytes(b'broken cache')
    before = inventory(project)
    from specroad.work import evaluation as module
    native = module._evaluate; seen = []
    def observed(current, task, call):
        assert task['unit_id'] not in first.executed_unit_ids
        seen.append(task['unit_id']); return native(current, task, call)
    monkeypatch.setattr(module, '_evaluate', observed)
    while store.read().entries('remaining'): advance(store)
    result = finalize_evaluation_work(store, registry=registry())
    assert json.loads(result.outcome_bytes)['result']['results'] == direct(inputs, jobs)
    assert len(seen) == len(jobs) - 1 and inventory(project) == before
    after = inventory(tmp_path)
    def forbidden(*args, **kwargs): raise AssertionError('Completed native work was repeated')
    monkeypatch.setattr(module, '_evaluate', forbidden)
    again, _ = advance(store, size=100, profile='standard')
    final = finalize_evaluation_work(store, registry=registry())
    assert again.executed_unit_ids == () and final.outcome_bytes == result.outcome_bytes
    assert final.manifest.raw == result.manifest.raw and inventory(tmp_path) == after


@pytest.mark.parametrize('flag', ['--step-cpu-ms', '--step-wall-ms'])
def test_exceeded_soft_window_persists_one_real_unit(recorded, tmp_path, flag):
    _, jobs, _, _, _, initial, _, store = setup(tmp_path)
    result, measurement = advance(store, size=100, sampler=ticking(), options={flag: 1})
    assert len(result.executed_unit_ids) == 1 and measurement['soft_budget_exceeded']
    assert len(result.manifest.entries('remaining')) == len(jobs) - 1
    assert result.manifest.as_dict()['checkpoint_generation'] == initial.as_dict()['checkpoint_generation'] + 1


@pytest.mark.parametrize('count_done', [0, 1, 4])
def test_incomplete_batch_cannot_finalize_or_write_a_false_completion(recorded, tmp_path, count_done):
    _, _, _, _, _, _, _, store = setup(tmp_path)
    for _ in range(count_done): advance(store)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        finalize_evaluation_work(store, registry=registry())
    assert caught.value.reason == 'unfinished_evaluation_cannot_complete'
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('size', [True, 0, -1, '1'])
def test_invalid_window_is_rejected_without_work_effects(recorded, tmp_path, size):
    _, _, _, _, _, _, _, store = setup(tmp_path); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError): advance(store, size=size)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('kind', ['missing_profile', 'malformed_model', 'srx_type'])
def test_real_failed_checks_preserve_checkpoint_and_complete_findings(recorded, tmp_path, kind):
    inputs, jobs, _ = data()
    if kind == 'missing_profile': jobs[0]['core_profile'] = 'missing@0.2.0'
    elif kind == 'malformed_model': inputs[0]['raw'] = b'{"broken":'
    else:
        jobs = [jobs[1]]; jobs[0]['program'] = expression_document({'op': 'add', 'args': [literal('bad'), literal(1)]})
    _, _, _, project, _, initial, _, store = setup(tmp_path, input_data=inputs, job_data=jobs)
    before = inventory(project)
    if kind == 'malformed_model':
        with pytest.raises(WorkEvaluationBlocked) as caught: advance(store)
        value = caught.value.as_dict()
        assert value['exit_code'] == 3 and value['observation']['checks_complete'] is False
        assert value['observation']['diagnostics'] and value['observation']['source_report']['stages'][0]['diagnostics']
    elif kind == 'srx_type':
        with pytest.raises(SrxError) as caught: advance(store)
        assert caught.value.diagnostic()['code'] == 'SRV110'
    else:
        from specroad.profiles.composition_values import ProfileCompositionError
        with pytest.raises(ProfileCompositionError): advance(store)
    assert store.read().raw == initial.raw and inventory(project) == before


def test_new_incompatible_build_cannot_write_or_reuse_evaluation(recorded, tmp_path, monkeypatch):
    _, _, _, _, _, _, _, store = setup(tmp_path); advance(store)
    monkeypatch.setattr(_build, 'BUILD_METADATA', {**_build.BUILD_METADATA, 'build_sha256': 'b' * 64})
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught: advance(store)
    assert caught.value.exit_code == 6 and inventory(tmp_path) == before


@pytest.mark.parametrize('size', [1, 100])
def test_complete_policy_failures_retain_all_native_findings_in_final_result(recorded, tmp_path, size):
    inputs, jobs, values = data()
    inputs[-1]['raw'] = artifact_bytes(profile_data(profile_id='core', forbidden_fields=[
        {'artifact_types': ['goal'], 'maturities': [], 'fields': ['/statement']}]))
    _, _, _, project, _, _, _, store = setup(tmp_path, input_data=inputs, job_data=jobs)
    before = inventory(project)
    while store.read().entries('remaining'): advance(store, size=size)
    result = finalize_evaluation_work(store, registry=registry()); document = json.loads(result.outcome_bytes)
    expected = direct(inputs, jobs)
    assert result.command_exit_code == 1 and document['status'] == 'failed'
    assert document['summary']['complete'] is True and document['summary']['failure_kind'] == 'policy'
    assert document['result']['results'] == expected
    diagnostics = expected[0]['observation']['diagnostics']
    assert document['diagnostics'] == diagnostics and len(diagnostics) == 3
    assert {d['artifact_id'] for d in diagnostics} == {v['id'] for v in values[:3]}
    assert inventory(project) == before
    assert finalize_evaluation_work(store, registry=registry()).outcome_bytes == result.outcome_bytes


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


@pytest.mark.parametrize('kind', ['module', 'zipapp'])
def test_real_distribution_reuses_saved_units_in_new_processes_and_relocated_roots(tmp_path, kind):
    import os
    inputs, jobs, _ = data(); project = tmp_path / 'project'
    for item in inputs:
        p = project / item['root_id'] / item['path']; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(item['raw'])
    packet = tmp_path / 'independent-binding.json'
    packet.write_text(json.dumps({'inputs': [{**i, 'raw': i['raw'].hex()} for i in inputs], 'jobs': jobs}))
    output = tmp_path / 'distribution'; root = Path(__file__).resolve().parents[1]
    built = subprocess.run([sys.executable, '-I', '-B', str(root / 'tools/build_core.py'), '--output', str(output)], capture_output=True)
    assert built.returncode == 0, built.stderr
    distribution = output / ('module' if kind == 'module' else 'specroad.pyz')
    work = tmp_path / 'work'; cwd = tmp_path / 'unrelated'; cwd.mkdir()
    environment = {'PATH': ''}
    if 'LD_LIBRARY_PATH' in os.environ: environment['LD_LIBRARY_PATH'] = os.environ['LD_LIBRARY_PATH']
    def invoke(action, profile='constrained'):
        body = 'import sys;sys.path.insert(0,' + repr(str(distribution)) + ');' + PORTABLE
        child = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', body, str(packet), str(work), str(project), action, profile],
            cwd=cwd, env=environment, stdin=subprocess.DEVNULL, capture_output=True)
        assert child.returncode == 0, child.stderr
        return json.loads(child.stdout)
    assert invoke('plan')['generation'] == 0
    first = invoke('advance'); assert len(first['executed']) == 1
    moved = tmp_path / 'moved-distribution'; distribution.rename(moved); distribution = moved
    moved = tmp_path / 'moved-work'; work.rename(moved); work = moved
    moved = tmp_path / 'moved-project'; project.rename(moved); project = moved
    for item in inputs: (project / item['root_id'] / item['path']).unlink()
    before = inventory(project); executed = list(first['executed'])
    for index in range(1, len(jobs)):
        step = invoke('advance', 'standard' if index % 2 else 'constrained')
        assert step['generation'] == index + 1 and len(step['executed']) == 1
        assert not set(step['executed']).intersection(executed); executed += step['executed']
    result = invoke('finalize'); again = invoke('finalize')
    assert result == again and result['generation'] == len(jobs) + 1
    assert result['outcome']['result']['results'] == direct(inputs, jobs)
    assert result['outcome']['summary']['complete'] is True and inventory(project) == before
    assert invoke('advance')['executed'] == []


def test_native_single_transaction_matches_work_preparation_and_receipt_replay(recorded, tmp_path):
    from specroad.work import publication
    from specroad.changes.authoring import bind_plan_authoring
    from specroad.changes.idempotency import resolve_normative_request
    from specroad.storage.project import ProjectSource
    from support.publication import ALLOW, files
    from test_work_publication import setup as native_setup, ready, publish
    left = native_setup(tmp_path / 'single', multi=True)
    right = native_setup(tmp_path / 'stepped', multi=True)
    model, plan, preflight, _, _, _, _ = left
    assert plan.source_bytes == right[1].source_bytes
    transaction = 'txn-work-parity'
    with publication.project_lock(model.binding.source_root, kind='writer', command='change apply',
            project_id=model.binding.project_id, request_id=plan.data['request_id'], transaction_id=transaction) as held:
        building = publication.begin_building_journal(preflight, held_lock=held, transaction_id=transaction, authority=ALLOW)
        staged = publication.stage_building_journal(preflight, building, held_lock=held, authority=ALLOW)
        published = publication.publish_prepared_journal(preflight, staged, held_lock=held, authority=ALLOW)
        journal = publication.read_committing_journal(ProjectSource(model.binding.source_root), transaction,
            expected_sha256=published.data['journal_sha256'], preflight=preflight)
        publication.finalize_committing_journal(preflight, journal, held_lock=held, authority=ALLOW)
        publication.cleanup_completed_transaction(preflight, transaction, held_lock=held, authority=ALLOW)
    expected = resolve_normative_request(ProjectSource(model.binding.source_root), bind_plan_authoring(plan)).data
    model2, plan2, _, reg, _, _, store = right
    ready(store, reg, model2, plan2)
    actual = publish(store, reg, model2, plan2, transaction_id=transaction).as_dict()
    assert files(Path(model.binding.source_root)) == files(Path(model2.binding.source_root))
    assert actual['result_object'] == expected['result_object']
    before = inventory(tmp_path)
    with no_write_attempts():
        replay = publish(store, reg, model2, plan2, transaction_id='unused-replay')
    assert replay.as_dict()['result_object'] == actual['result_object'] and inventory(tmp_path) == before
    assert len(list((Path(model2.binding.source_root) / '.specroad/requests').glob('*.json'))) == 1
