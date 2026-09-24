"""Negative CI observations, real evidence bytes, pagination and exact attempts."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO, StringIO
import json
from types import SimpleNamespace
import subprocess
import zipfile
import pytest
from watch_bundle_ci import (Request, CIObservationError, GhClient, records, observe_ci,
    inspect_report_archive, pack_evidence, emit_evidence, recover_evidence)
from test_ci_wait import Client, SHA, REPO, run_value, jobs_value, zip_bytes

SOURCE = 'c' * 64


def report_value(version='3.10', workers=4):
    ids = ['tests/test_synthetic.py::test_ok']
    outcomes = {ids[0]: 'passed'}
    return {'report_format_version':2, 'purpose':'development_behavior_evidence', 'suite_passed':True,
        'run_id':f'{version}-{workers}', 'tests_run':1, 'test_outcomes':outcomes,
        'tool_build_sha256':SOURCE, 'platform_sha256':'d'*64, 'specification_sha256':'e'*64, 'catalog_sha256':'f'*64,
        'runtime':{'implementation':'cpython','python':version+'.1'}, 'execution':{'workers':workers},
        'observation':{'nodeids':ids,'nodeid_to_test_id':{ids[0]:ids[0]}, 'test_outcomes':outcomes,
            'worker_test_counts':{'gw0':1}, 'suite_passed':True, 'errors':[], 'pytest_exit_code':0, 'tests_run':1}}


def report_zip(version='3.10', mode='parallel', changes=None):
    p=report_value(version); p.update(changes or {})
    files={'parallel-evidence.json':json.dumps(p).encode()}
    if mode=='both':
        s=report_value(version,0)
        files['serial-evidence.json']=json.dumps(s).encode()
        files['summary.json']=json.dumps({'suite_passed':True,'exit_code':0,'errors':[],
            'comparison':{'equivalent':True,'runs':2,'tests':1}}).encode()
    return zip_bytes(files)


class ArtifactClient(Client):
    def __init__(self,mode='parallel',**kw):
        super().__init__(jobs=jobs_value(mode),**kw)
        self.artifacts=[]; self.archives={}
        for i,v in enumerate(range(10,15),1):
            raw=report_zip('3.'+str(v),mode)
            self.artifacts.append({'id':100+i,'name':f'behavior-3.{v}-{SHA}-attempt-1','expired':False,
                'digest':'sha256:'+sha256(raw).hexdigest(),
                'workflow_run':{'id':51,'head_sha':SHA,'head_branch':'dev'}})
            self.archives[100+i]=raw
    def document(self,path):
        if '/artifacts?' in path:
            return {'total_count':len(self.artifacts),'artifacts':deepcopy(self.artifacts)}
        return super().document(path)
    def get(self,path):
        if '/artifacts/' in path:
            return self.archives[int(path.split('/')[-2])]
        return super().get(path)


@pytest.mark.parametrize('mode,bundle',[('parallel',19),('both',20)])
def test_complete_matrix_reports_and_logs_are_preserved(mode,bundle):
    client=ArtifactClient(mode)
    summary,files=observe_ci(Request(SHA,bundle,SOURCE),client=client,sleeper=lambda _:None)
    assert summary['ci_status']=='success' and summary['evidence_complete'] and summary['test_evidence_verified']
    assert len(summary['test_reports'])==5
    assert all(x['tests_run']==1 for x in summary['test_reports'])
    assert {k for k in files if k.startswith('reports-')}=={f'reports-3.{v}.zip' for v in range(10,15)}
    assert files['reports-3.10.zip']==client.archives[101]
    assert (summary['test_reports'][0]['comparison'] is not None) is (mode=='both')


@pytest.mark.parametrize('change',[{'suite_passed':False},{'tests_run':0},{'tool_build_sha256':'b'*64},
    {'runtime':{'implementation':'cpython','python':'3.14.1'}}, {'execution':{'workers':8}},
    {'test_outcomes':{'tests/test_synthetic.py::test_ok':'skipped'}}])
def test_bad_reports_never_become_verified(change):
    with pytest.raises(ValueError):inspect_report_archive(report_zip(changes=change),Request(SHA,19,SOURCE),'3.10')


def test_missing_artifacts_keep_actual_ci_conclusion_but_not_evidence_success():
    summary,files=observe_ci(Request(SHA,19,SOURCE),client=Client(),sleeper=lambda _:None)
    assert summary['ci_status']=='success' and summary['github_conclusion']=='success'
    assert not summary['evidence_complete'] and not summary['test_evidence_verified']
    assert len(summary['errors'])==5 and 'logs.zip' in files


@pytest.mark.parametrize('change',[{'expired':True},{'digest':'sha256:'+'0'*64},
    {'workflow_run':{'id':52,'head_sha':SHA,'head_branch':'dev'}}, {'name':f'behavior-3.10-{SHA}-attempt-2'}])
def test_expired_tampered_or_wrong_attempt_artifact_not_substituted(change):
    client=ArtifactClient();client.artifacts[0].update(change)
    summary,_=observe_ci(Request(SHA,19,SOURCE),client=client,sleeper=lambda _:None)
    assert not summary['evidence_complete'] and not summary['test_evidence_verified']
    assert len(summary['test_reports'])==4


def test_duplicate_matching_artifact_not_arbitrarily_selected():
    client=ArtifactClient();a=deepcopy(client.artifacts[0]);a['id']=601;client.artifacts.append(a)
    summary,_=observe_ci(Request(SHA,19,SOURCE),client=client,sleeper=lambda _:None)
    assert not summary['test_evidence_verified']


def test_pagination_complete_and_inconsistent_pages_rejected():
    class Pages:
        def __init__(self,broken=False):self.broken=broken
        def document(self,path):
            second='page=2' in path
            ids=range(101,132) if second else range(1,101)
            if self.broken and second:ids=range(100,131)
            return {'total_count':131,'jobs':[{'id':i} for i in ids]}
    assert len(records(Pages(),'jobs','jobs'))==131
    with pytest.raises(CIObservationError):records(Pages(True),'jobs','jobs')


def test_run_attempt_change_during_capture_is_not_green():
    class Changed(ArtifactClient):
        def __init__(self):super().__init__();self.n=0
        def document(self,path):
            if path.endswith('/runs/51'):
                self.n+=1
                return run_value(run_attempt=1 if self.n==1 else 2)
            return super().document(path)
    summary,files=observe_ci(Request(SHA,19,SOURCE),client=Changed(),sleeper=lambda _:None)
    assert summary['ci_status']=='unavailable' and not summary['evidence_complete']
    assert 'logs.zip' in files and summary['errors'][-1]['reason']=='run_attempt_changed'


def test_api_failure_retry_retains_no_false_success():
    class Broken(Client):
        def document(self,path):raise CIObservationError('gh_api_exit_1')
    sleeps=[]
    summary,files=observe_ci(Request(SHA,19),client=Broken(),sleeper=sleeps.append)
    assert summary['ci_status']=='unavailable' and len(sleeps)==2
    assert json.loads(files['summary.json'])['local_apply']=='success'


def test_interrupted_observer_does_not_cancel_github_or_change_commits():
    class Interrupted(Client):
        def document(self,path):raise KeyboardInterrupt()
    summary,files=observe_ci(Request(SHA,19),client=Interrupted(),sleeper=lambda _:None)
    assert summary['ci_status']=='observation_interrupted'
    assert 'summary.json' in files and summary['local_apply']=='success'


def test_failed_ci_archives_failed_reports_without_claiming_a_pass():
    client=ArtifactClient(run=run_value(conclusion='failure'))
    raw=report_zip(changes={'suite_passed':False});client.archives[101]=raw
    client.artifacts[0]['digest']='sha256:'+sha256(raw).hexdigest()
    summary,files=observe_ci(Request(SHA,19,SOURCE),client=client,sleeper=lambda _:None)
    assert summary['ci_status']=='failed' and not summary['test_evidence_verified']
    assert files['reports-3.10.zip']==raw


def test_invalid_logs_report_missing_capture_separately():
    client=ArtifactClient();client.logs=b'not zip'
    summary,_=observe_ci(Request(SHA,19,SOURCE),client=client,sleeper=lambda _:None)
    assert summary['ci_status']=='success' and not summary['logs_captured'] and not summary['evidence_complete']


def test_missing_gh_and_communication_timeout_are_explicit():
    def absent(*a,**k):raise FileNotFoundError('gh')
    def timeout(*a,**k):raise subprocess.TimeoutExpired(['gh'],90)
    for runner in (absent,timeout):
        with pytest.raises(CIObservationError):GhClient(runner).get('repos/'+REPO+'/actions/runs/51')


def test_empty_missing_serial_or_false_comparison_is_rejected():
    with pytest.raises(CIObservationError):inspect_report_archive(zip_bytes(),Request(SHA,20,SOURCE),'3.10')
    with pytest.raises(CIObservationError):inspect_report_archive(report_zip(),Request(SHA,20,SOURCE),'3.10')
    p=report_value();s=report_value(workers=0)
    raw=zip_bytes({'parallel-evidence.json':json.dumps(p).encode(),'serial-evidence.json':json.dumps(s).encode(),
                   'summary.json':b'{"suite_passed":true,"comparison":{"equivalent":false}}'})
    with pytest.raises(CIObservationError):inspect_report_archive(raw,Request(SHA,20,SOURCE),'3.10')


def test_opaque_archive_member_path_is_not_extracted(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    raw=zip_bytes({'../../outside':b'never write','parallel-evidence.json':json.dumps(report_value()).encode()})
    assert inspect_report_archive(raw,Request(SHA,19,SOURCE),'3.10')['tests_run']==1
    assert list(tmp_path.iterdir())==[]


def test_evidence_multiple_chunks_survive_and_corruption_is_rejected():
    import random
    raw=pack_evidence({'raw.bin':random.Random(7).randbytes(14000)})
    stream=StringIO();emit_evidence(raw,stream);text=stream.getvalue()
    assert recover_evidence(text)==raw
    lines=text.splitlines();lines[1],lines[2]=lines[2],lines[1]
    with pytest.raises(CIObservationError):recover_evidence('\n'.join(lines))
    changed=text.replace('"bytes": '+str(len(raw)), '"bytes": '+str(len(raw)+1),1)
    with pytest.raises(CIObservationError):recover_evidence(changed)


def test_isolated_cli_push_failure_keeps_local_success_and_result_evidence(tmp_path):
    from pathlib import Path
    import sys
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run([sys.executable,'-I','-B',str(root/'tools/watch_bundle_ci.py'),
        '--commit',SHA,'--bundle','19','--push-failed','--output-dir',str(tmp_path/'local')],
        cwd=tmp_path,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    raw=recover_evidence(result.stdout.decode())
    assert raw==(tmp_path/'local/ci-evidence.zip').read_bytes()
    with zipfile.ZipFile(BytesIO(raw)) as z:
        assert json.loads(z.read('summary.json'))['ci_status']=='not_published'
    archive=tmp_path/'result.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr('logs/execution.log',result.stdout)
    out=tmp_path/'restored.zip'
    subprocess.run([sys.executable,'-I','-B',str(root/'tools/extract_ci_evidence.py'),str(archive),
                    '--output',str(out)],cwd=tmp_path,check=True)
    assert out.read_bytes()==raw
