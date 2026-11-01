"""CPU quota, priority and real small-run evidence boundaries."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from verification_support import cpu_capacity as cpu, host_execution as host
from test_host_test_execution import active_root, resources


def quota_fixture(tmp_path, version, *, root='/', group='/slice/job'):
    mount = tmp_path/'cgroup'; (mount/'slice/job').mkdir(parents=True)
    cgroup = tmp_path/'membership'
    cgroup.write_text(('0::' if version==2 else '2:cpu,cpuacct:')+group+'\n')
    mountinfo = tmp_path/'mountinfo'
    kind = 'cgroup2 cgroup2 rw' if version==2 else 'cgroup cgroup rw,cpu,cpuacct'
    mountinfo.write_text(f'1 2 0:32 {root} {mount} rw - {kind}\n')
    return mount,cgroup,mountinfo


@pytest.mark.parametrize('version',[1,2])
def test_cgroup_parent_quota_caps_unlimited_child(tmp_path,monkeypatch,version):
    monkeypatch.setattr(cpu.sys,'platform','linux')
    mount,cgroup,info=quota_fixture(tmp_path,version)
    if version==2:
        (mount/'slice/cpu.max').write_text('250000 100000')
        (mount/'slice/job/cpu.max').write_text('max 100000')
    else:
        for directory,quota in [(mount/'slice','250000'),(mount/'slice/job','-1')]:
            (directory/'cpu.cfs_quota_us').write_text(quota)
            (directory/'cpu.cfs_period_us').write_text('100000')
    assert cpu.cgroup_limits(cgroup,info)==[2]


@pytest.mark.parametrize('quota,expected',[('50000 100000',1),('100000 100000',1),('900000 100000',9)])
def test_fractional_quota_never_prevents_one_worker(tmp_path,monkeypatch,quota,expected):
    monkeypatch.setattr(cpu.sys,'platform','linux')
    mount,cgroup,info=quota_fixture(tmp_path,2)
    (mount/'slice/job/cpu.max').write_text(quota)
    assert cpu.cgroup_limits(cgroup,info)==[expected]


def test_cgroup_subtree_mount_resolves_its_actual_root(tmp_path,monkeypatch):
    monkeypatch.setattr(cpu.sys,'platform','linux')
    mount,cgroup,info=quota_fixture(tmp_path,2,root='/slice',group='/slice/job')
    (mount/'job').mkdir();(mount/'job/cpu.max').write_text('300000 100000')
    assert cpu.cgroup_limits(cgroup,info)==[3]


@pytest.mark.parametrize('value',['0 100000','-2 100000','max 0','max','1 2 extra','broken 100000'])
def test_malformed_visible_quota_does_not_silently_overbook(tmp_path,monkeypatch,value):
    monkeypatch.setattr(cpu.sys,'platform','linux')
    mount,cgroup,info=quota_fixture(tmp_path,2)
    (mount/'slice/job/cpu.max').write_text(value)
    with pytest.raises(ValueError):cpu.cgroup_limits(cgroup,info)


def test_affinity_and_ancestor_quotas_both_limit_logical_cpus(monkeypatch):
    monkeypatch.setattr(cpu.os,'cpu_count',lambda:32)
    monkeypatch.setattr(cpu.os,'sched_getaffinity',lambda _:set(range(6)))
    monkeypatch.setattr(cpu,'cgroup_limits',lambda:[8,3])
    assert cpu.available_cpus()==3
    monkeypatch.setattr(cpu,'cgroup_limits',lambda:[])
    assert cpu.available_cpus()==6


@pytest.mark.parametrize('fault',['symlink','parent-link','hardlink','duplicate','unknown','oversized'])
def test_policy_corruption_is_rejected_before_test_execution(tmp_path,fault):
    root=active_root(tmp_path);path=root/host.POLICY
    if fault in ('symlink','hardlink'):
        original=tmp_path/'original';original.write_bytes(path.read_bytes());path.unlink()
        if fault=='symlink':path.symlink_to(original)
        else:path.hardlink_to(original)
    elif fault=='parent-link':
        original=root/'verification';target=root/'real';original.rename(target);original.symlink_to(target)
    elif fault=='duplicate':path.write_text('{"format_version":1,"format_version":1,"worker_limit":10,"nice_minimum":10}')
    elif fault=='unknown':path.write_text('{}')
    else:path.write_text(' '*5000)
    with pytest.raises(ValueError):host.select_workers(root)


def test_failed_priority_change_stops_before_any_test_context(monkeypatch,tmp_path):
    root=active_root(tmp_path)
    monkeypatch.delenv(host.NESTED,raising=False)
    monkeypatch.setattr(host,'available_cpus',lambda:8)
    monkeypatch.setattr(host.os,'getpriority',lambda *a:0)
    monkeypatch.setattr(host.os,'setpriority',lambda *a:None)
    values={'collectonly':False,'numprocesses':None,'worker_limit':10,'dist':'worksteal'}
    config=SimpleNamespace(option=SimpleNamespace(),getoption=lambda k,default=None:values.get(k,default))
    with pytest.raises(ValueError):host.configure_pytest(config,root)
    assert host.NESTED not in os.environ


def test_direct_xdist_request_cannot_leave_an_oversized_process_list(monkeypatch,tmp_path):
    root=active_root(tmp_path)
    monkeypatch.delenv(host.NESTED,raising=False)
    monkeypatch.setattr(host,'available_cpus',lambda:32)
    monkeypatch.setattr(host,'lower_priority',lambda:10)
    values={'collectonly':False,'numprocesses':32,'worker_limit':10,'dist':'worksteal','maxprocesses':6}
    config=SimpleNamespace(option=SimpleNamespace(tx=['popen']*32),
                           getoption=lambda k,default=None:values.get(k,default))
    result=host.configure_pytest(config,root)
    assert result['workers']==6 and config.option.numprocesses==6 and len(config.option.tx)==6


@pytest.mark.parametrize('nested',['0','1'])
def test_real_selected_run_inherits_priority_and_durably_records_each_phase(tmp_path,nested):
    from support.catalog_project import make_catalog_project,execute
    from verification_support.runtime_history import RuntimeHistory
    ids=[f'tests/test_subject.py::test_{i}' for i in range(3)]
    source='import os, subprocess, sys\n'+''.join(
        f'def test_{i}():\n'
        '    assert os.getpriority(os.PRIO_PROCESS,0)>=10\n'
        '    assert os.environ["SPECROAD_NESTED_TEST_RUN"]=="1"\n'
        '    child=subprocess.check_output([sys.executable,"-I","-c","import os;print(os.getpriority(os.PRIO_PROCESS,0))"])\n'
        '    assert int(child)>=10\n' for i in range(3))
    root=make_catalog_project(tmp_path/'repo',ids=ids,source=source)
    (root/host.POLICY).write_text(json.dumps(host.POLICY_VALUE))
    out=root/'build/selected'
    process=execute(root,'run_selected_tests.py',['--test-file','tests/test_subject.py','--expected-tests','3',
        '--outdir',str(out),'--worker-limit','2'],environment={host.NESTED:nested})
    assert process.returncode==0,(process.stdout+process.stderr).decode()
    report=json.loads((out/'selection.json').read_bytes())
    count,proof=host.select_workers(root,worker_limit=2,environment={host.NESTED:nested})
    assert report['selected_passed'] and report['workers']==count
    host.verify_resources(report['observation'],proof)
    with RuntimeHistory(root) as history:
        assert history.db.execute('SELECT workers,exit_code FROM runs').fetchall()==[(count,0)]
        assert history.db.execute('SELECT COUNT(*) FROM phases').fetchone()==(9,)


def test_real_ci_job_uses_execution_host_and_aggregate_accepts_its_receipt(tmp_path,monkeypatch):
    from support.catalog_project import make_catalog_project,check
    from verification_support import ci_package_runtime as runtime
    from verification_support.ci_packages import make_plan,DEFAULT_RULES
    from ci_support.contract import Request
    from ci_support.evidence import inspect_report_archive
    from test_ci_packages import context
    from test_ci_wait import zip_bytes
    monkeypatch.setenv(host.NESTED,'0')
    ids=[f'tests/test_subject.py::test_{i}' for i in range(4)]
    source=''.join(f'def test_{i}():\n    assert {i}>=0\n' for i in range(4))
    root=make_catalog_project(tmp_path/'repo',ids=ids,source=source)
    (root/host.POLICY).write_text(json.dumps(host.POLICY_VALUE))
    code,catalog=check(root);assert code==0
    ctx=context(f'{sys.version_info.major}.{sys.version_info.minor}')
    estimates={'format_version':1,'kind':'specroad-ci-runtime-estimates-v1',
               'tests':[{'test_id':i,'duration_ns':1000} for i in ids]}
    plan=make_plan(catalog,estimates,ctx,rules={**DEFAULT_RULES,'workers':1},host_resources=resources(1,2))
    path=root/'build/plan.json';path.write_text(json.dumps(plan))
    monkeypatch.setattr(runtime,'execution_context',lambda *a:ctx)
    out=root/'build/package';receipt=runtime.run_package(root,path,0,out)
    expected,proof=host.select_workers(root,worker_limit=2,environment={})
    assert receipt['workers']==expected and receipt['host_resources']==proof
    target=root/'build/full';report=runtime.aggregate(root,path,[out/'package-result.json'],target)
    assert report['suite_passed'] and report['tests_run']==4
    request=Request(ctx['test_commit_sha'],537,plan['bindings']['source_sha256'],
        expected_mode='parallel',workflow_commit=ctx['workflow_commit_sha'])
    files={p.name:p.read_bytes() for p in target.glob('*.json')}
    assert inspect_report_archive(zip_bytes(files),request,ctx['python'],run_id=123,attempt=1)['tests_run']==4


@pytest.mark.parametrize('fault',[None,'nice','workers'])
def test_unpartitioned_ci_evidence_also_binds_actual_host_resources(fault):
    from ci_support.contract import Request,CIObservationError
    from ci_support.evidence import inspect_report_archive
    from test_ci_wait_right import report_value,SOURCE,SHA
    from test_ci_wait import zip_bytes
    report=report_value(workers=2);actual={**resources(2),'nice_actual':10}
    report['execution']['host_resources']=deepcopy(actual)
    report['observation'].update(host_resources=actual,workers=['gw0','gw1'])
    if fault=='nice':report['observation']['host_resources']['nice_actual']=0
    elif fault=='workers':report['execution']['workers']=4
    raw=zip_bytes({'parallel-evidence.json':json.dumps(report).encode()})
    request=Request(SHA,537,SOURCE,event='push',expected_mode='parallel')
    if fault is not None:
        with pytest.raises(CIObservationError):inspect_report_archive(raw,request,'3.10')
    else:
        assert inspect_report_archive(raw,request,'3.10')['tests_run']==1
