"""Required tests override rotation/filter; stages commit only after exact gates."""
import base64
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from verification_support import apply_rotation as rotation
from verification_support import apply_gate
from verification_support.commit_tests import (
    POLICY, POLICY_VALUE, SCOPE, validate_plan, resolve_required, union_selection,
)
from verification_support.runtime_history import RuntimeHistory, LOCAL, filter_latest
from verification_support.bundle_apply import (
    canonical, public_plan, remaining_commits, run_bundle, validate_bundle,
)
from verification_support.bundle_prepare import render_entrypoint
from test_apply_thirds import thirds
from test_apply_rotation import NEXT
from test_runtime_history import complete


def make_plan(ids=None, files=None, commit_id='step.W'):
    return {'format_version': 1, 'commit_id': commit_id, 'test_ids': ids or [],
            'test_files': files or [], 'reason': 'Exercise the changed behavior and its regressions'}


def test_required_slow_and_other_group_tests_are_unioned_once():
    pairs = {f'tests/test_sample.py::case.{i}': f'case.{i}' for i in range(10)}
    filtered = {n: i for n, i in pairs.items() if i in {'case.0', 'case.3', 'case.6'}}
    selected, receipt = union_selection(filtered, pairs,
        make_plan(['case.0', 'case.8', 'case.9']), {'excluded_test_ids': ['case.8', 'case.9']})
    assert set(selected.values()) == {'case.0', 'case.3', 'case.6', 'case.8', 'case.9'}
    assert receipt['extra_test_ids'] == ['case.8', 'case.9']
    assert receipt['restored_slow_test_ids'] == ['case.8', 'case.9']
    assert receipt['rotation_tests'] == 3


def test_required_file_includes_all_collected_cases_and_deduplicates_id():
    pairs = {'tests/test_a.py::one': 'legacy.one', 'tests/test_a.py::two[p]': 'native.two',
             'tests/test_b.py::one': 'other'}
    assert resolve_required(make_plan(['legacy.one'], ['tests/test_a.py']), pairs) == {
        n: i for n, i in pairs.items() if i != 'other'}


@pytest.mark.parametrize('fault', ['empty', 'duplicate', 'unknown', 'version', 'commit', 'traversal', 'newline'])
def test_invalid_required_plan_is_rejected(fault):
    plan = make_plan(['case.0'])
    if fault == 'empty': plan['test_ids'] = []
    elif fault == 'duplicate': plan['test_ids'] *= 2
    elif fault == 'unknown': plan['other'] = True
    elif fault == 'version': plan['format_version'] = True
    elif fault == 'commit': plan['commit_id'] = 'step.R'
    elif fault == 'traversal': plan['test_files'] = ['tests/../test_a.py']
    else: plan['test_ids'] = ['case.0\n--option']
    with pytest.raises(ValueError): validate_plan(plan, 'step.W')


@pytest.mark.parametrize('plan', [make_plan(['gone']), make_plan(files=['tests/test_gone.py'])])
def test_missing_required_selector_never_becomes_a_smaller_success(plan):
    with pytest.raises(ValueError): resolve_required(plan, {'tests/test_a.py::x': 'present'})


def setup_gate(tmp_path, monkeypatch):
    root = tmp_path/'repo'; (root/'verification').mkdir(parents=True)
    pairs = {f'tests/test_sample.py::case.{i}': f'case.{i}' for i in range(12)}
    registry = thirds(sorted(pairs.values()))
    (root/rotation.REGISTRY).write_text(json.dumps(registry))
    (root/POLICY).write_bytes(canonical(POLICY_VALUE))
    (root/'verification/test_runtime_policy.json').write_text(json.dumps({
        'format_version': 1, 'selection': 'latest_valid_fifth', 'database': LOCAL}))
    with RuntimeHistory(root) as history:
        for i in range(12): complete(history, history.begin('a'*64, 4), f'case.{i}', seconds=i)
    monkeypatch.setattr(rotation, 'run_catalog_preflight', lambda r,p: p.write_text(json.dumps({
        'source_sha256': 'a'*64, 'collected_tests': 12, 'nodeid_to_test_id': pairs,
        'catalog_valid': True, 'collection_exit_code': 0, 'errors': [], 'tests_run': 0})) or True)
    monkeypatch.setattr(rotation, 'commit_context', lambda *a: (NEXT, 2, registry))
    monkeypatch.setattr(rotation, 'source_identity', lambda *a: 'a'*64)
    monkeypatch.setattr(apply_gate, 'commit_context', lambda *a: (NEXT, 2, registry))
    monkeypatch.setattr(apply_gate, 'source_identity', lambda *a: 'a'*64)
    plan = make_plan(['case.3', 'case.10', 'case.11'])
    path = tmp_path/'test-plan.json'; path.write_bytes(canonical(plan))
    return root, pairs, plan, path


@pytest.mark.parametrize('fault', [None, 'missing', 'failed', 'plan-change', 'source-change'])
def test_gate_and_independent_verifier_bind_the_actual_union(tmp_path, monkeypatch, fault):
    root, pairs, plan, path = setup_gate(tmp_path, monkeypatch)
    out = tmp_path/'gate'
    def execute(command, **kwargs):
        nodes = (out/'nodeids.txt').read_text().splitlines()
        selected = {n: pairs[n] for n in nodes}
        assert set(selected.values()) == {'case.3', 'case.6', 'case.9', 'case.10', 'case.11'}
        assert command[command.index('--dist')+1] == 'worksteal'
        if fault == 'missing': selected.pop(next(iter(selected)))
        outcomes = {i: 'passed' for i in selected.values()}
        if fault == 'failed': outcomes['case.10'] = 'failed'
        observation = dict(observation_format_version=1, engine='pytest', nodeids=list(selected),
            nodeid_to_test_id=selected, test_outcomes=outcomes, suite_passed=True, errors=[],
            tests_run=len(selected), pytest_exit_code=0, worker_test_counts={'gw0':len(selected), 'gw1':0})
        (out/'observations.json').write_text(json.dumps(observation))
        if fault == 'plan-change': path.write_bytes(canonical(make_plan(['case.3'])))
        if fault == 'source-change': monkeypatch.setattr(rotation, 'source_identity', lambda *a: 'b'*64)
        return SimpleNamespace(returncode=0)
    report = rotation.run_apply_partition(root, out, test_plan=path, commit_id='step.W', runner=execute)
    assert report['selected_passed'] is (fault is None)
    assert report['selection_binding']['format_version'] == 4
    assert report['test_scope'] == SCOPE
    if fault is None:
        proof = apply_gate.verify_commit_gate(root, out, source='a'*64, head=NEXT, test_plan=plan)
        assert proof['tests'] == 5 and proof['required_tests'] == 3


def test_policy_requires_plan_before_any_test_execution(tmp_path, monkeypatch):
    root, _, _, _ = setup_gate(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        rotation.run_apply_partition(root, tmp_path/'gate', runner=lambda *a,**k: pytest.fail('no execution'))


def test_required_test_can_rescue_a_fully_filtered_partition():
    pairs = {f'tests/test_a.py::test_{i}': f'case.{i}' for i in range(10)}
    snapshot = {'format_version':1, 'kind':'specroad-latest-runtime-snapshot-v1',
                'tests':[{'test_id':f'case.{i}', 'duration_ns':i} for i in range(10)]}
    partition = {n:i for n,i in pairs.items() if i == 'case.9'}
    filtered, runtime = filter_latest(partition, snapshot, allow_empty=True)
    assert not filtered
    selected, _ = union_selection(filtered, pairs, make_plan(['case.9']), runtime)
    assert selected == partition


def bundle():
    stages=[]
    for index, kind in enumerate(('W','R','C')):
        content = str(index).encode(); identifier = 'step.'+kind
        stages.append({'commit_id':identifier, 'message':'OFF-PLAN '+identifier,
            'before':{}, 'after':{'sample.py':sha256(content).hexdigest()},
            'payloads':{'sample.py':base64.b64encode(content).decode()}, 'source_sha256':'a'*64,
            'test_plan':make_plan(['case.0'], commit_id=identifier)})
    return {'format_version':1, 'bundle_number':'535', 'source_result_sha256':'f'*64,
            'binding':{'repo_id':'a33ed6cf-0a97-4b73-b11a-d4239e7a2145','base_commit':'a'*40,
                       'state_fingerprint':'7c9d2a24e397e0e5','fingerprint_algorithm':'patchharbor-state-v1'},
            'apply_repository':'/fixture/specroad-apply','branch':'dev','initial_dirty':False,
            'stages':stages,'correction_of':None}


class Backend:
    def __init__(self, fail=None):
        self.current='a'*40; self.fail=fail; self.calls=[]; self.events=[]
    def head(self): return self.current
    def publish_plan(self, plan): self.plan=deepcopy(plan)
    def publish(self, event): self.events.append(deepcopy(event))
    def initial(self, data): self.current=data['binding']['base_commit']
    def before(self, stage, head): assert self.current==head
    def install(self, stage): self.calls.append(('install',stage['commit_id']))
    def pending(self, stage, head): assert self.current==head
    def test(self, stage, head):
        self.calls.append(('test',stage['commit_id']))
        if stage['commit_id']==self.fail: raise ValueError('test failed')
        return {'selection_sha256':'c'*64}
    def commit(self, stage, head, evidence):
        self.calls.append(('commit',stage['commit_id']))
        self.current=sha256((head+stage['commit_id']).encode()).hexdigest()[:40]
        return self.current
    def clean(self, head): assert self.current==head


def test_three_real_stages_are_tested_before_their_own_commit():
    backend=Backend(); result=run_bundle(bundle(),backend)
    assert backend.calls==[(action,'step.'+kind) for kind in ('W','R','C') for action in ('install','test','commit')]
    assert result['phase']=='completed' and result['remaining_commit_ids']==[]
    assert len(result['committed'])==3


def test_failed_middle_stage_preserves_first_commit_and_supplies_complete_rest():
    data=bundle(); backend=Backend('step.R')
    with pytest.raises(ValueError): run_bundle(data,backend)
    progress=backend.events[-1]
    remaining=remaining_commits(backend.plan, progress, result_head=backend.head())
    assert [s['commit_id'] for s in remaining]==['step.R','step.C']
    assert ('commit','step.W') in backend.calls and ('commit','step.R') not in backend.calls
    assert ('install','step.C') not in backend.calls
    correction=deepcopy(data); correction['binding']['base_commit']=backend.head()
    correction['source_result_sha256']='e'*64; correction['initial_dirty']=True
    correction['stages']=correction['stages'][1:]
    correction['correction_of']={'plan_sha256':progress['plan_sha256'], 'remaining_commit_ids':['step.R','step.C']}
    resumed=Backend(); result=run_bundle(correction,resumed)
    assert result['phase']=='completed'
    assert all(identifier!='step.W' for _,identifier in resumed.calls)


def test_unproved_commit_after_error_is_not_automatically_replayed():
    backend=Backend('step.R')
    with pytest.raises(ValueError): run_bundle(bundle(),backend)
    with pytest.raises(ValueError):
        remaining_commits(backend.plan,backend.events[-1],result_head='e'*40)


def test_payload_tampering_prevents_all_apply_actions():
    data=bundle(); data['stages'][0]['payloads']['sample.py']=base64.b64encode(b'changed').decode()
    backend=Backend()
    with pytest.raises(ValueError): run_bundle(data,backend)
    assert not backend.calls and not backend.events


def test_entrypoint_generation_does_not_execute_prepared_work(tmp_path):
    script=render_entrypoint(bundle(),core_python='/installed/core/python')
    assert script.startswith(b'#!/usr/bin/env bash\n# PATCHHARBOR\n')
    code=script.split(b"<<'SPECROAD_APPLY_COMMIT_PLAN'\n",1)[1].rsplit(b'\nSPECROAD_APPLY_COMMIT_PLAN',1)[0]
    compile(code, '<prepared-entrypoint>', 'exec')
    assert not list(tmp_path.iterdir())
