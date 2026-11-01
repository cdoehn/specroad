"""Host resource selection and bound evidence; no timing/speed assertions."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from verification_support import host_execution as host
from verification_support.ci_packages import (
    DEFAULT_RULES, PYTHONS, make_plan, matrix, merge_shards, validate_plan, estimate_on_host,
)
from test_ci_packages import inputs, context, receipts


def active_root(tmp_path):
    root = tmp_path / 'repo'
    (root / 'verification').mkdir(parents=True)
    (root / host.POLICY).write_text(json.dumps(host.POLICY_VALUE))
    return root


def resources(cpus, limit=10, *, nested=False):
    return dict(format_version=1, available_cpus=cpus, worker_limit=limit,
                workers=1 if nested else min(cpus, limit), nested=nested, nice_minimum=10)


@pytest.mark.parametrize('cpus,limit,requested,nested,wanted', [
    (32,10,None,False,10), (4,10,None,False,4), (32,24,None,False,24),
    (1,10,None,False,1), (16,10,3,False,3), (16,10,None,True,1),
])
def test_host_cpu_count_limit_and_nested_budget(tmp_path, monkeypatch, cpus,limit,requested,nested,wanted):
    root = active_root(tmp_path)
    monkeypatch.setattr(host, 'available_cpus', lambda: cpus)
    count, proof = host.select_workers(root, requested, worker_limit=limit,
                                      environment={host.NESTED:'1' if nested else '0'})
    assert count == wanted and proof['workers'] == wanted
    assert proof['available_cpus'] == cpus and proof['worker_limit'] == limit
    assert host.validate_resources(proof) == proof


@pytest.mark.parametrize('limit', [0,-1,True,1.5,'10',None])
def test_invalid_limit_rejected_before_test_process(tmp_path, limit):
    with pytest.raises(ValueError):
        host.select_workers(active_root(tmp_path), worker_limit=limit)


@pytest.mark.parametrize('initial,expected_calls', [(0,[10]),(10,[]),(15,[])])
def test_nice_is_at_least_ten_and_never_raises_existing_priority(monkeypatch, initial, expected_calls):
    current = [initial]; calls = []
    monkeypatch.setattr(host.os, 'getpriority', lambda *a: current[0])
    def set_priority(which, who, value):
        calls.append(value); current[0] = value
    monkeypatch.setattr(host.os, 'setpriority', set_priority)
    assert host.lower_priority() == max(initial,10)
    assert calls == expected_calls


@pytest.mark.parametrize('fault', ['missing','workers','nice','limit','cpus'])
def test_observation_cannot_hide_wrong_resources(fault):
    expected=resources(8); observed=dict(workers=['gw'+str(i) for i in range(8)],
                                       host_resources={**expected,'nice_actual':10})
    if fault=='missing': observed.pop('host_resources')
    elif fault=='workers': observed['workers'].pop()
    elif fault=='nice': observed['host_resources']['nice_actual']=0
    elif fault=='limit': observed['host_resources']['worker_limit']=9
    else: observed['host_resources']['available_cpus']=16
    with pytest.raises(ValueError):host.verify_resources(observed,expected)


@pytest.mark.parametrize('workers', [1,2,10])
def test_ci_package_plan_uses_its_planning_host_capacity(workers):
    collection,estimates=inputs([1000]*60)
    plan=make_plan(collection,estimates,context(),
                   rules={**DEFAULT_RULES,'workers':workers},host_resources=resources(workers))
    assert validate_plan(plan)==plan and plan['format_version']==2
    assert sorted(i for s in plan['shards'] for i in s['tests'])==list(range(60))
    assert all(s['estimated_seconds']<=10800 for s in plan['shards'])


def heterogeneous_plan_and_receipts():
    collection,estimates=inputs([1000]*60)
    plan=make_plan(collection,estimates,context(),rules={**DEFAULT_RULES,'workers':4},
                   host_resources=resources(4))
    result=receipts(plan)
    for i,receipt in enumerate(result):
        actual=resources(2 if i % 2 else 16)
        receipt.update(format_version=2,kind='specroad-ci-package-result-v2',
                       workers=actual['workers'],host_resources=actual,
                       estimated_seconds_actual_host=estimate_on_host(plan,i,actual['workers']))
        receipt['observation'].update(workers=['gw'+str(n) for n in range(actual['workers'])],
                                      host_resources={**actual,'nice_actual':10})
    return plan,result


def test_ci_jobs_can_have_more_or_fewer_cpus_than_the_planner():
    plan,result=heterogeneous_plan_and_receipts()
    assert {r['workers'] for r in result}=={2,10}
    observed,_=merge_shards(plan,result)
    assert observed['tests_run']==60 and observed['suite_passed'] is True


def test_python_planning_jobs_may_also_have_different_cpu_counts():
    plans = [make_plan(*inputs([100]*30), context(version),
                      rules={**DEFAULT_RULES,'workers':i+1}, host_resources=resources(i+1))
             for i,version in enumerate(PYTHONS)]
    result = matrix(plans)
    assert {row['python'] for row in result['include']} == set(PYTHONS)
    assert len(result['include']) == sum(len(p['shards']) for p in plans)


@pytest.mark.parametrize('fault', ['too-few','different-limit','low-priority','estimate'])
def test_heterogeneous_ci_still_requires_its_maximal_bounded_workers(fault):
    plan,result=heterogeneous_plan_and_receipts();receipt=result[0]
    if fault=='too-few':
        receipt['host_resources']['workers']=1;receipt['workers']=1
    elif fault=='different-limit':receipt['host_resources']['worker_limit']=20
    elif fault=='low-priority':receipt['observation']['host_resources']['nice_actual']=0
    else:receipt['estimated_seconds_actual_host']+=1
    with pytest.raises(ValueError):merge_shards(plan,result)


def test_one_xdist_worker_remains_a_valid_durable_measurement():
    from verification_support.runtime_measurement import validate_measurement
    from test_runtime_baseline import measurement
    value=measurement();value['workers']=1
    assert validate_measurement(value)==value


def test_manual_cli_limit_reaches_the_child_process(tmp_path,monkeypatch):
    import run_tests
    root=active_root(tmp_path)
    monkeypatch.setattr(run_tests,'ROOT',root)
    monkeypatch.setattr(host,'available_cpus',lambda:32)
    monkeypatch.delenv(host.NESTED,raising=False)
    calls=[]
    def launch(command,**kwargs):
        calls.append(command);return SimpleNamespace(returncode=0)
    monkeypatch.setattr(run_tests.subprocess,'run',launch)
    assert run_tests.main(['--worker-limit','6'])==0
    assert calls[0][calls[0].index('-n')+1]=='6'
    assert calls[0][calls[0].index('--worker-limit')+1]=='6'
