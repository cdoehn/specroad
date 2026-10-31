"""Real package execution, exact attempt evidence, failures and durable timings."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import sys

import pytest

from test_ci_packages import context, inputs, plan, receipts
from verification_support.ci_packages import (
    DEFAULT_RULES, PYTHONS, digest, make_plan, matrix, merge_shards, validate_plan,
)


def resign(value):
    value['plan_sha256'] = digest({k:v for k,v in value.items() if k != 'plan_sha256'})


@pytest.mark.parametrize('field', ['source_sha256','specification_sha256','catalog_sha256'])
def test_matrix_rejects_different_inputs_even_when_commit_label_matches(field):
    plans = [plan(version=v) for v in PYTHONS]
    plans[-1]['bindings'][field] = 'f'*64
    resign(plans[-1])
    with pytest.raises(ValueError, match='Mixed source'):
        matrix(plans)


@pytest.mark.parametrize('field', ['shard','estimated_seconds','test_index'])
def test_plan_rejects_boolean_indices_or_estimates(field):
    p = plan([1])
    if field == 'test_index': p['shards'][0]['tests'][0] = False
    else: p['shards'][0][field] = False
    resign(p)
    with pytest.raises(ValueError): validate_plan(p)


@pytest.mark.parametrize('change', [
    {'errors':['worker_lost']}, {'process_exit_code':1}, {'process_exit_code':False},
    {'shard':-1}, {'shard':False}, {'workers':8},
])
def test_package_receipt_cannot_hide_failed_execution_or_unknown_worker(change):
    p = plan(); r = receipts(p); r[0].update(change)
    with pytest.raises(ValueError): merge_shards(p,r)


@pytest.mark.parametrize('rules', [
    {'workers':8}, {'max_matrix_jobs':257}, {'target_seconds':18001},
    {'duration_factor':float('nan')}, {'duration_factor':0.9},
])
def test_invalid_planning_policy_never_produces_matrix(rules):
    with pytest.raises(ValueError): plan(**rules)


def test_python_specific_collection_can_grow_without_losing_other_versions():
    _, estimates = inputs([1000]*68)
    plans = [make_plan(inputs([1000]*(20+i*12))[0],estimates,context(v))
             for i,v in enumerate(PYTHONS)]
    combined = matrix(plans)
    assert len(plans[-1]['shards']) > len(plans[0]['shards'])
    assert len(combined['include']) == sum(len(p['shards']) for p in plans)


def test_new_tests_without_measurements_automatically_add_packages():
    c,e = inputs([None]*200)
    e['tests'] = []
    p = make_plan(c,e,context())
    assert len(p['shards']) > 1
    assert sum(len(s['tests']) for s in p['shards']) == 200
    assert all(t['duration_ns'] is None for t in p['tests'])


def test_durable_backup_keeps_partial_attempts_and_rejects_source_or_links(tmp_path):
    from verification_support.runtime_history import RuntimeHistory
    from verification_support.ci_package_runtime import preserve_history, export_estimates
    root = tmp_path/'root'; root.mkdir()
    with RuntimeHistory(root) as h:
        run = h.begin('a'*64,4)
        h.start(run,'tests/test_a.py::test_x','new','gw0')
        h.observe(run,'tests/test_a.py::test_x','new','gw0','setup',0.1,'passed')
    output = root/'build/partial.sqlite3'
    preserve_history(root,output)
    with sqlite3.connect(output) as db:
        assert db.execute('SELECT complete FROM attempts').fetchall() == [(0,)]
        assert db.execute('SELECT phase FROM phases').fetchall() == [('setup',)]
    assert export_estimates(output,['new'])['tests'] == [dict(test_id='new',duration_ns=None)]
    with pytest.raises(FileExistsError): preserve_history(root,output)
    with pytest.raises(ValueError): preserve_history(root,root/'tracked.sqlite3')
    (tmp_path/'link').symlink_to(root/'build',target_is_directory=True)
    with pytest.raises(ValueError): preserve_history(root,tmp_path/'link/unsafe.sqlite3')


def test_three_real_packages_merge_to_full_evidence_and_observer_rejects_missing_receipts(tmp_path,monkeypatch):
    from support.catalog_project import make_catalog_project,check
    from verification_support import ci_package_runtime as runtime
    from ci_support.contract import Request, CIObservationError
    from ci_support.evidence import inspect_report_archive
    from test_ci_wait import zip_bytes
    source = '\n'.join(f'def test_{i}():\n    assert {i} >= 0\n' for i in range(12))
    ids = [f'tests/test_subject.py::test_{i}' for i in range(12)]
    root = make_catalog_project(tmp_path/'fixture',ids=ids,source=source)
    code,catalog = check(root); assert code == 0
    ctx = context(f'{sys.version_info.major}.{sys.version_info.minor}')
    estimates = dict(format_version=1,kind='specroad-ci-runtime-estimates-v1',tests=[
        dict(test_id=t,duration_ns=100_000_000_000) for t in ids])
    p = make_plan(catalog,estimates,ctx,rules={**DEFAULT_RULES,
        'duration_factor':1,'target_seconds':101,'overhead_seconds':1})
    assert len(p['shards']) == 3
    plan_path = root/'build/plan.json'; plan_path.write_text(json.dumps(p))
    monkeypatch.setattr(runtime,'execution_context',lambda *args: ctx)
    paths = []
    for s in p['shards']:
        out = root/f'build/package-{s["shard"]}'
        receipt = runtime.run_package(root,plan_path,s['shard'],out)
        assert receipt['selected_passed'] and receipt['full_suite_passed'] is None
        assert receipt['observation']['tests_run'] == 4
        paths.append(out/'package-result.json')
    merged = root/'build/full'
    report = runtime.aggregate(root,plan_path,paths,merged)
    assert report['suite_passed'] and report['tests_run'] == 12
    request = Request(ctx['test_commit_sha'],525,p['bindings']['source_sha256'],
        expected_mode='parallel',workflow_commit=ctx['workflow_commit_sha'])
    files = {f.name:f.read_bytes() for f in merged.glob('*.json')}
    result = inspect_report_archive(zip_bytes(files),request,ctx['python'],run_id=123,attempt=1)
    assert result['tests_run'] == 12 and result['source_bound']
    backup = root/'build/history.sqlite3'; runtime.preserve_history(root,backup)
    with sqlite3.connect(backup) as db:
        assert db.execute('SELECT COUNT(*) FROM attempts WHERE complete=1').fetchone() == (12,)
        assert db.execute('SELECT COUNT(*) FROM phases').fetchone() == (36,)
    with pytest.raises(ValueError,match='Missing CI packages'):
        runtime.aggregate(root,plan_path,paths[:-1],root/'build/incomplete')
    assert not (root/'build/incomplete').exists()
    del files['shard-receipts.json']
    with pytest.raises(CIObservationError,match='invalid_package_aggregate'):
        inspect_report_archive(zip_bytes(files),request,ctx['python'],run_id=123,attempt=1)


def test_failed_process_still_writes_a_failed_package_receipt(tmp_path,monkeypatch):
    from verification_support import ci_package_runtime as runtime
    p = plan(); path = tmp_path/'plan.json'; path.write_text(json.dumps(p))
    monkeypatch.setattr(runtime,'execution_context',lambda *args:p['context'])
    def preflight(root,output):
        output.write_text('{}'); return True
    monkeypatch.setattr(runtime,'run_catalog_preflight',preflight)
    monkeypatch.setattr(runtime,'verify_plan_inputs',lambda *args:None)
    def cannot_start(*args,**kwargs): raise OSError('interpreter unavailable')
    result = runtime.run_package(tmp_path,path,0,tmp_path/'build/failed',runner=cannot_start)
    assert not result['selected_passed'] and result['full_suite_passed'] is None
    assert result['errors'] == ['package_process_not_started','nonpassing_or_unbound_package']
    assert (tmp_path/'build/failed/package-result.json').is_file()
