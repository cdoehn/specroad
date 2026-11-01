"""Actual parallel gate/measurement integration and tampered continuation evidence."""
import base64
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pytest

from support.catalog_project import make_catalog_project, execute
from verification_support import apply_gate
from verification_support import apply_rotation as rotation
from verification_support.bundle_apply import canonical, remaining_commits, run_bundle, validate_bundle
from verification_support.bundle_prepare import prepare_stage
from verification_support.commit_tests import POLICY, POLICY_VALUE, read_object
from verification_support.identity import source_identity
from verification_support.runtime_history import RuntimeHistory, LOCAL
from test_apply_commit_plan import Backend, bundle, make_plan, setup_gate
from test_apply_rotation import NEXT


@pytest.mark.parametrize('failing', [False, True])
@pytest.mark.parametrize('host_policy', [False, True])
def test_real_parallel_union_records_every_phase_and_red_gate_keeps_head(tmp_path, failing, host_policy):
    ids = [f'tests/test_subject.py::test_{i}' for i in range(9)]
    source = '\n'.join(f'def test_{i}():\n    assert {not (failing and i == 8)}\n' for i in range(9))
    root = make_catalog_project(tmp_path/'repo', ids=ids, source=source)
    (root/'.gitignore').write_text('build/\n__pycache__/\n*.pyc\n')
    (root/'verification/test_runtime_policy.json').write_bytes(canonical({
        'format_version':1,'selection':'latest_valid_fifth','database':LOCAL}))
    (root/POLICY).write_bytes(canonical(POLICY_VALUE))
    if host_policy:
        from verification_support import host_execution as host
        (root/host.POLICY).write_bytes(canonical(host.POLICY_VALUE))
    hooks = root/'build/empty-hooks'; hooks.mkdir()
    def git(*args):
        return subprocess.run(['git', '-c', 'user.name=Apply Fixture', '-c', 'user.email=fixture@example.invalid',
                               '-c', 'core.hooksPath='+str(hooks), *args], cwd=root,
                              stdin=subprocess.DEVNULL, capture_output=True, check=True).stdout
    git('init'); git('add','--','.'); git('commit','-m','fixture base')
    head = git('rev-parse','HEAD').decode().strip()
    registry = {'format_version':2,'anchor_commit':head,'rotation_anchor_commit':head,
                'partition_count':3,'test_ids':ids}
    (root/rotation.REGISTRY).write_bytes(canonical(registry))
    with RuntimeHistory(root) as history:
        seed = history.begin('d'*64,4)
        for i,identity in enumerate(ids):
            history.start(seed,identity,identity,'gw0')
            for phase in ('setup','call','teardown'):
                history.observe(seed,identity,identity,'gw0',phase,i+1,'passed')
        history.finish(seed,0)
    plan = make_plan([ids[1],ids[8]])
    plan_path = root/'build/plan.json'; plan_path.write_bytes(canonical(plan))
    expected_source = source_identity(root)
    out = root/'build/gate'
    process = execute(root,'run_apply_tests.py',['--test-plan',str(plan_path),
        '--commit-id','step.W','--outdir',str(out),'--worker-limit','2'],
        environment={'SPECROAD_NESTED_TEST_RUN':'0'})
    assert process.returncode == (1 if failing else 0), (process.stdout+process.stderr).decode()
    report = json.loads((out/'selection.json').read_bytes())
    selected = {ids[i] for i in (0,1,3,6,8)}
    assert set(report['nodeid_to_test_id'].values()) == selected
    assert report['required_tests']['restored_slow_test_ids'] == [ids[8]]
    assert report['full_suite_passed'] is None
    if host_policy:
        count, resources = host.select_workers(root,worker_limit=2,environment={})
        assert report['host_resources'] == resources and report['workers'] == count
        observed = json.loads((out/'observations.json').read_bytes())
        host.verify_resources(observed,resources)
        assert observed['host_resources']['nice_actual'] >= 10
        assert report['format_version'] == 4
    assert git('rev-parse','HEAD').decode().strip() == head
    with RuntimeHistory(root) as history:
        run = history.db.execute('SELECT MAX(id) FROM runs').fetchone()[0]
        rows = history.db.execute('SELECT test,complete,invalid FROM attempts WHERE run=?',(run,)).fetchall()
        assert {r[0] for r in rows} == selected and len(rows) == 5
        assert history.db.execute('SELECT COUNT(*) FROM phases p JOIN attempts a ON p.attempt=a.id WHERE a.run=?',(run,)).fetchone()[0] == 15
        assert sum(bool(r[2]) for r in rows) == int(failing)
    if not failing:
        proof = apply_gate.verify_commit_gate(root,out,source=expected_source,head=head,test_plan=plan)
        assert proof['tests'] == 5 and proof['required_tests'] == 2


@pytest.mark.parametrize('fault', ['source-result', 'reorder', 'missing-rest', 'invented-commit', 'plan'])
def test_corrupt_partial_result_cannot_drop_or_replay_commits(fault):
    backend=Backend('step.R')
    with pytest.raises(ValueError): run_bundle(bundle(),backend)
    progress=deepcopy(backend.events[-1]); plan=deepcopy(backend.plan)
    if fault=='source-result': progress['source_result_sha256']='0'*64
    elif fault=='reorder': progress['committed'][0]['commit_id']='step.R'
    elif fault=='missing-rest': progress['remaining_commit_ids']=['step.R']
    elif fault=='invented-commit': progress['committed'][0]['commit']='a'*40
    else: plan['stages'][1]['test_plan']['reason']='changed'
    with pytest.raises(ValueError): remaining_commits(plan,progress,result_head=backend.head())


@pytest.mark.parametrize('fault', ['wrong-id', 'duplicate-id', 'unknown-file', 'binding', 'payload'])
def test_invalid_bundle_is_rejected_before_materialization(fault):
    data=bundle()
    if fault=='wrong-id': data['stages'][0]['test_plan']['commit_id']='different'
    elif fault=='duplicate-id': data['stages'].append(deepcopy(data['stages'][0]))
    elif fault=='unknown-file':
        stage=data['stages'][0]; stage['after']['tests/test_new.py']=sha256(b'new').hexdigest()
        stage['payloads']['tests/test_new.py']=base64.b64encode(b'new').decode()
    elif fault=='binding': data['binding']['state_fingerprint']='short'
    else: data['stages'][0]['payloads']['sample.py']='!'
    with pytest.raises(ValueError): validate_bundle(data)


def test_correction_may_not_omit_remaining_integration_stage():
    data=bundle(); data['stages']=data['stages'][1:]
    data['correction_of']={'plan_sha256':'f'*64,'remaining_commit_ids':['step.R']}
    with pytest.raises(ValueError): validate_bundle(data)


@pytest.mark.parametrize('fault', ['duplicate-key', 'nan', 'symlink', 'hardlink', 'parent-link'])
def test_test_plan_file_rejects_ambiguous_or_linked_input(tmp_path,fault):
    source=tmp_path/'source.json'; source.write_bytes(canonical(make_plan(['case.0'])))
    path=tmp_path/'plan.json'
    if fault=='duplicate-key': path.write_text('{"a":1,"a":2}')
    elif fault=='nan': path.write_text('{"a":NaN}')
    elif fault=='symlink': path.symlink_to(source)
    elif fault=='hardlink': path.hardlink_to(source)
    else:
        link=tmp_path/'linked'; link.symlink_to(tmp_path,target_is_directory=True)
        path=link/'source.json'
    with pytest.raises(ValueError): read_object(path)


@pytest.mark.parametrize('fault', ['plan', 'snapshot', 'observation', 'receipt'])
def test_rechecked_gate_rejects_changes_to_successful_reports(tmp_path,monkeypatch,fault):
    root,pairs,plan,path=setup_gate(tmp_path,monkeypatch);out=tmp_path/'gate'
    def execute_gate(command,**kwargs):
        nodes=(out/'nodeids.txt').read_text().splitlines(); selected={n:pairs[n] for n in nodes}
        (out/'observations.json').write_bytes(canonical(dict(observation_format_version=1,engine='pytest',
            nodeids=nodes,nodeid_to_test_id=selected,test_outcomes={i:'passed' for i in selected.values()},
            suite_passed=True,errors=[],tests_run=len(nodes),pytest_exit_code=0,worker_test_counts={'gw0':len(nodes)})))
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0)
    rotation.run_apply_partition(root,out,test_plan=path,commit_id='step.W',runner=execute_gate)
    if fault=='plan': plan['reason']='different selection justification'
    elif fault=='snapshot':
        p=out/'runtime-snapshot.json';v=json.loads(p.read_bytes());v['tests'][0]['duration_ns']=999999999999;p.write_bytes(canonical(v))
    elif fault=='observation':
        p=out/'observations.json';v=json.loads(p.read_bytes());v['test_outcomes']['case.10']='skipped';p.write_bytes(canonical(v))
    else:
        p=out/'selection.json';v=json.loads(p.read_bytes());v['selection_sha256']='0'*64;p.write_bytes(canonical(v))
    with pytest.raises(ValueError): apply_gate.verify_commit_gate(root,out,source='a'*64,head=NEXT,test_plan=plan)
