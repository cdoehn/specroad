"""Time-balanced exact partitions and complete cross-job behavior evidence."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

from verification_support.ci_packages import (
    DEFAULT_RULES, PYTHONS, digest, make_plan, matrix, merge_shards, selected_pairs, validate_plan,
)


def context(version='3.14'):
    return dict(format_version=1,repository='cdoehn/specroad',branch='dev',event='workflow_dispatch',
        mode='parallel',python=version,test_commit_sha='a'*40,workflow_commit_sha='b'*40,
        run_id=123,run_attempt=1)


def inputs(durations):
    pairs = {f'tests/test_sample.py::test_{i:04d}':f'case.{i:04d}' for i in range(len(durations))}
    collection = dict(catalog_valid=True,errors=[],tests_run=0,collection_exit_code=0,
        full_suite_passed=None,collected_tests=len(pairs),nodeid_to_test_id=pairs,
        source_sha256='c'*64,catalog_sha256='d'*64,specification_sha256='e'*64)
    estimates = dict(format_version=1,kind='specroad-ci-runtime-estimates-v1',tests=[
        dict(test_id=t,duration_ns=None if d is None else round(d*1e9))
        for t,d in zip(pairs.values(),durations)])
    return collection,estimates


def plan(durations=(10,20,30,40),version='3.14',**rules):
    return make_plan(*inputs(durations),context(version),rules={**DEFAULT_RULES,**rules})


def receipts(p):
    result=[]
    for shard in p['shards']:
        pairs=selected_pairs(p,shard['shard'])
        observation=dict(observation_format_version=1,engine='pytest',nodeids=list(pairs),
            nodeid_to_test_id=pairs,test_outcomes={t:'passed' for t in pairs.values()},
            suite_passed=True,errors=[],tests_run=len(pairs),pytest_exit_code=0,
            workers=['gw0'],worker_test_counts={'gw0':len(pairs)})
        result.append(dict(format_version=1,kind='specroad-ci-package-result-v1',context=p['context'],
            plan_sha256=p['plan_sha256'],bindings=p['bindings'],shard=shard['shard'],workers=4,
            distribution='worksteal',runtime=dict(implementation='cpython',python=p['context']['python']+'.4',
                system='Linux',machine='x86_64'),selected_passed=True,full_suite_passed=None,
            exit_code=0,process_exit_code=0,errors=[],observation=observation))
    return result


def test_growing_suite_automatically_adds_balanced_packages_without_losing_tests():
    small=plan([1000]*20);large=plan([1000]*60)
    assert len(large['shards'])>len(small['shards'])
    assigned=[i for s in large['shards'] for i in s['tests']]
    assert sorted(assigned)==list(range(60))
    assert max(s['estimated_seconds'] for s in large['shards'])<=10800
    assert max(s['estimated_seconds'] for s in large['shards'])-min(s['estimated_seconds'] for s in large['shards'])<=1500


def test_long_tests_are_spread_across_jobs_and_initial_worksteal_queues():
    p=plan([5000]*8+[0.1]*800)
    assert len(p['shards'])>=2
    for shard in p['shards']:
        indices=shard['tests'];remaining=len(indices);offset=0
        loads=[]
        for left in range(4,0,-1):
            size=remaining//left;queue=indices[offset:offset+size]
            values=[p['tests'][i]['estimate_ns'] for i in queue]
            assert values==sorted(values,reverse=True)
            loads.append(sum(values));remaining-=size;offset+=size
        assert max(loads)<=9900*1e9


def test_unknown_and_invalid_current_durations_are_included_conservatively():
    p=plan([None,0,1])
    assert p['tests'][0]['estimate_ns']==450_000_000_000
    assert len([i for s in p['shards'] for i in s['tests']])==3


def test_plan_is_deterministic_under_collection_and_estimate_input_order():
    c,e=inputs([1000]*42)
    a=make_plan(c,e,context())
    c['nodeid_to_test_id']=dict(reversed(list(c['nodeid_to_test_id'].items())))
    b=make_plan(c,e,context())
    assert a==b and validate_plan(a)==a


def test_matrix_contains_every_python_package_once():
    plans=[plan([1000]*40,version=v) for v in PYTHONS]
    m=matrix(list(reversed(plans)))
    assert len(m['include'])==sum(len(p['shards']) for p in plans)
    assert len({(r['python'],r['shard']) for r in m['include']})==len(m['include'])


@pytest.mark.parametrize('change',[{'run_attempt':2},{'test_commit_sha':'f'*40},{'workflow_commit_sha':'f'*40}])
def test_matrix_rejects_plans_from_other_attempt_or_revision(change):
    plans=[plan(version=v) for v in PYTHONS]
    plans[-1]['context'].update(change)
    plans[-1]['plan_sha256']=digest({k:v for k,v in plans[-1].items() if k!='plan_sha256'})
    with pytest.raises(ValueError):matrix(plans)


def test_one_oversized_test_cannot_be_fixed_by_silently_exceeding_target():
    with pytest.raises(ValueError,match='single test'):plan([8000])


def test_matrix_limit_rejects_instead_of_dropping_tests():
    with pytest.raises(ValueError,match='256'):plan([6000]*300)


def test_merge_reconstructs_one_complete_native_observation():
    p=plan([1000]*60)
    merged,runtime=merge_shards(p,list(reversed(receipts(p))))
    assert merged['tests_run']==60 and merged['suite_passed']
    assert len(merged['test_outcomes'])==60
    assert sum(merged['worker_test_counts'].values())==60
    assert runtime['python']=='3.14.4'


@pytest.mark.parametrize('fault',['missing','duplicate','failed','wrong_test','skip','other_commit','other_attempt','other_python','missing_phase'])
def test_partial_or_mixed_packages_never_produce_full_success(fault):
    p=plan([1000]*60);r=receipts(p)
    if fault=='missing':r.pop()
    elif fault=='duplicate':r[-1]=deepcopy(r[0])
    elif fault=='failed':r[0]['selected_passed']=False
    elif fault=='wrong_test':r[0]['observation']['nodeid_to_test_id']['unexpected']='unexpected'
    elif fault=='skip':r[0]['observation']['test_outcomes'][next(iter(r[0]['observation']['test_outcomes']))]='skipped'
    elif fault=='missing_phase':r[0]['observation']['suite_passed']=False
    elif fault=='other_python':r[0]['runtime']['python']='3.13.4'
    else:
        r[0]['context']=dict(r[0]['context'])
        r[0]['context']['test_commit_sha' if fault=='other_commit' else 'run_attempt']='f'*40 if fault=='other_commit' else 2
    with pytest.raises(ValueError):merge_shards(p,r)


def test_changed_assignment_is_rejected_even_with_recomputed_hash():
    p=plan([1000]*60)
    p['shards'][0]['tests'].pop()
    p['plan_sha256']=digest({k:v for k,v in p.items() if k!='plan_sha256'})
    with pytest.raises(ValueError):validate_plan(p)


def test_export_reuses_first_dev_measurement_and_never_resurrects_old_success(tmp_path):
    from verification_support.runtime_history import RuntimeHistory
    from verification_support.ci_package_runtime import export_estimates
    from test_runtime_history import complete
    with RuntimeHistory(tmp_path) as history:
        complete(history,history.begin('a'*64,4),'existing',seconds=2)
        complete(history,history.begin('a'*64,4),'broken',seconds=2)
        history.start(history.begin('a'*64,4),'tests/test_sample.py::broken','broken','gw0')
        path=history.path
    before=path.read_bytes()
    value=export_estimates(path,['existing','broken','new'])
    assert {r['test_id']:r['duration_ns'] for r in value['tests']}=={'existing':6_000_000_000,'broken':None,'new':None}
    assert path.read_bytes()==before


def test_real_parallel_packages_collect_all_then_execute_only_bound_tests(tmp_path):
    from support.catalog_project import make_catalog_project,check,execute
    from verification_support.runtime_history import RuntimeHistory
    root=make_catalog_project(tmp_path)
    code,c=check(root)
    assert code==0
    estimates=dict(format_version=1,kind='specroad-ci-runtime-estimates-v1',tests=[
        dict(test_id=t,duration_ns=1_000_000_000) for t in c['nodeid_to_test_id'].values()])
    p=make_plan(c,estimates,context(f'{sys.version_info.major}.{sys.version_info.minor}'))
    path=root/'build/plan.json';path.write_text(json.dumps(p))
    out=root/'build/observation.json'
    process=execute(root,'pytest_entry.py',['-o','addopts=','-p','xdist.plugin','-n','4',
        '--dist','worksteal','--max-worker-restart=0','--sr-ci-plan',str(path),'--sr-ci-shard','0',
        '--sr-expected-tests','4','--sr-observations',str(out),str(root/'tests')])
    assert process.returncode==0,(process.stdout+process.stderr).decode()
    observed=json.loads(out.read_text())
    assert observed['nodeid_to_test_id']==c['nodeid_to_test_id']
    assert observed['tests_run']==4 and observed['suite_passed']
    with RuntimeHistory(root) as history:
        assert history.db.execute('SELECT COUNT(*) FROM phases').fetchone()==(12,)
