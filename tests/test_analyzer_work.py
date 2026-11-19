"""Durable public analyzer identity; test bodies run only at Apply gates."""
import json
from pathlib import Path

import pytest

from specroad.cli.application import dispatch_result
from specroad.cli.commands import builtin_registry
from specroad.cli.results import thaw
from specroad.runtime.consumption import WorkConsumption, CounterSample
from specroad.work.open_existing import open_existing_work
from specroad.analyzers.requests import AnalyzerRequest
from specroad.analyzers.packages import ReportPackage
from specroad.work.analyzer import checked
from support.read_only import inventory
from test_analyzer_subjects import project
from test_analyzer_cli import BUILTIN, call, json_file


@pytest.fixture(autouse=True)
def recorded(monkeypatch):
    from specroad import _build
    # In-process compatibility fixture only; the separate process case below
    # uses an actual native build and its independently generated identity.
    monkeypatch.setattr(_build,'BUILD_METADATA',{'format_version':1,
        'hash_algorithm':'specroad-dev-payload-v1','build_sha256':'7'*64})


def early(args, cwd):
    samples = iter((0,))
    def sample():
        value = next(samples, 2000000)
        return CounterSample(value,value,1)
    return dispatch_result(['analyzer',*args,'--step-wall-ms','1'],cwd=cwd,
        consumption=WorkConsumption(sampler=sample))


def store_at(path):
    return open_existing_work(Path(path),registry=builtin_registry())


def finish(path, cwd):
    # Bound by the actual remaining units, not a timing/retry loop.
    store = store_at(path)
    initial = store.read()
    _, request, _ = checked(initial)
    upper = 10 + (len(request.data['subjects'])*len(request.data['analyzers']) if request else 100)
    for _ in range(upper):
        result = dispatch_result(['work','resume',str(path)],cwd=cwd)
        if result.exit_code != 8:
            return result
    raise AssertionError('Declared work did not finish')


@pytest.mark.parametrize('name',['request','run'])
@pytest.mark.parametrize('explicit',[False,True])
@pytest.mark.parametrize('identity',[None,'review-round-17'])
def test_early_generation_survives_reopen_without_finished_snapshot(tmp_path,monkeypatch,name,explicit,identity):
    root=tmp_path/'project'; project(root)
    temporary=tmp_path/'temporary';temporary.mkdir();monkeypatch.setenv('TMPDIR',str(temporary))
    before=inventory(root)
    args=[name,'--project',str(root),'--analyzer',BUILTIN]
    if explicit:args+=['--work-dir',str(tmp_path/'work')]
    if identity is not None:args+=['--analysis-id',identity]
    result=early(args,tmp_path)
    assert result.exit_code==8 and result.complete is False and result.result is None, result.as_dict()
    path=Path(result.continuation.claim.work_dir)
    assert path==(tmp_path/'work') if explicit else path.parent==temporary
    store=store_at(path); current=store.read(); value=current.as_dict()
    saved=value['normalized_arguments']['analysis_id']
    assert saved==identity if identity is not None else saved.startswith('AN-')
    assert result.details['analysis_id']==saved
    assert value['checkpoint_generation']==0 and value['phase']=='snapshot'
    assert checked(current)[1] is None
    assert all(value[key] is None for key in ('actor','request_id','operations_sha256','plan_binding'))
    assert result.details['checkpoint_sha256']==value['checkpoint_sha256']
    assert 'next_action' not in result.details
    summary=result.as_dict()['summary']
    assert summary['next_action']=={'command_id':'work.resume','arguments':{'work_dir':str(path)}}
    assert summary['checkpoint']==str(path/'work.json')
    assert summary['analysis_id']==saved
    completed=finish(path,tmp_path)
    assert completed.exit_code==(0 if name=='request' else 5)
    data=thaw(completed.result)['data']
    request=AnalyzerRequest(json.dumps(data if name=='request' else data['request']).encode())
    assert request.data['request_id']==saved and len(request.data['subjects'])==2
    assert inventory(root)==before
    assert store_at(path).read().as_dict()['state']=='completed'


def test_explicit_projectless_request_keeps_its_existing_id(tmp_path):
    root=tmp_path/'project';project(root)
    first=call(['request','--analyzer',BUILTIN,'--analysis-id','foreign-id'],root)
    path=tmp_path/'input.json';json_file(path,thaw(first.result))
    result=early(['run','--request',str(path),'--work-dir',str(tmp_path/'work')],tmp_path)
    assert result.exit_code==8 and result.details['analysis_id']=='foreign-id'
    complete=finish(result.continuation.claim.work_dir,tmp_path)
    assert complete.exit_code==5
    package=ReportPackage(json.dumps(thaw(complete.result)['data']).encode())
    assert package.request.data['request_id']=='foreign-id'
    expected=AnalyzerRequest(json.dumps(thaw(first.result)).encode())
    expected_keys=sorted(subject['subject_key'] for subject in expected.data['subjects'])
    assert len(expected_keys)==2 and len(package.reports)==1
    assert package.request.canonical_bytes==expected.canonical_bytes
    for report in package.reports:
        assert report.data['coverage']=={
            'expected':expected_keys, 'open':expected_keys,
            'done':[], 'undetermined':[], 'failed':[],
            'counts':{'expected':2, 'open':2, 'done':0, 'undetermined':0, 'failed':0}}
        assert report.data['run_status']=='unavailable'
        assert [subject['subject_key'] for subject in report.data['subjects']]==expected_keys
        assert all(subject['status']=='open' for subject in report.data['subjects'])
    assert not (tmp_path/'.specroad').exists()


def test_existing_work_is_not_overwritten_by_a_new_analysis(tmp_path):
    root=tmp_path/'project';project(root);target=tmp_path/'work'
    first=early(['request','--project',str(root),'--analyzer',BUILTIN,'--work-dir',str(target)],tmp_path)
    assert first.exit_code==8
    before=inventory(target)
    second=early(['request','--project',str(root),'--analyzer',BUILTIN,'--work-dir',str(target)],tmp_path)
    assert second.exit_code in (5,6,7) and second.continuation is None
    assert inventory(target)==before


def test_real_distribution_keeps_early_id_across_independent_processes(tmp_path):
    import subprocess
    import sys
    root=tmp_path/'project';project(root);before=inventory(root)
    repository=Path(__file__).resolve().parents[1]
    distribution=tmp_path/'distribution'
    built=subprocess.run([sys.executable,'-I','-B',str(repository/'tools/build_core.py'),
        '--output',str(distribution)],capture_output=True,text=True)
    assert built.returncode==0,built.stderr
    script = """import json,sys
sys.path.insert(0,sys.argv[1])
from specroad.cli.application import dispatch_result
from specroad.cli.results import thaw
from specroad.runtime.consumption import WorkConsumption,CounterSample
if sys.argv[4]=='start':
 samples=iter((0,))
 def sample():
  value=next(samples,2000000);return CounterSample(value,value,1)
 result=dispatch_result(['analyzer','request','--project',sys.argv[2],
  '--analyzer','specroad.py3langid','--step-wall-ms','1','--work-dir',sys.argv[3]],
  consumption=WorkConsumption(sampler=sample))
 assert result.exit_code==8,result.as_dict()
 print(json.dumps({'id':result.details['analysis_id'],'code':result.exit_code}))
else:
 for turn in range(10):
  result=dispatch_result(['work','resume',sys.argv[3]])
  if result.exit_code!=8:break
 assert result.exit_code==0
 print(json.dumps({'id':thaw(result.result)['data']['request_id'],'code':result.exit_code}))
"""
    rows=[]
    for action in ('start','resume','reuse'):
        child=subprocess.run([sys.executable,'-I','-B','-c',script,str(distribution/'specroad.pyz'),
            str(root),str(tmp_path/'work'),action],capture_output=True,text=True)
        assert child.returncode==0,child.stderr
        rows.append(json.loads(child.stdout))
    assert rows[0]['id']==rows[1]['id']==rows[2]['id']
    assert rows[0]['id'].startswith('AN-') and inventory(root)==before
