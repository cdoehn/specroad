"""Adversarial launch inputs and actual portable worker execution."""
import json
import subprocess
from unittest.mock import patch
import pytest

from specroad.analyzers._values import AnalyzerError, encoded
from specroad.analyzers.requests import AnalyzerRequest, create_request
from specroad.analyzers.worker_transport import execute
from specroad.analyzers._execution import unavailable_package
from specroad.analyzers.packages import ReportPackage
from specroad.cli.results import thaw
from support.portable import build_distribution
from support.processes import run_python
from support.read_only import inventory
from test_analyzer_worker import request_value
from test_analyzer_subjects import project
from test_analyzer_cli import call, BUILTIN


def test_project_cwd_pythonpath_and_loader_environment_cannot_replace_worker(tmp_path,monkeypatch):
    marker=tmp_path/'executed'
    poison="from pathlib import Path\nPath("+repr(str(marker))+").write_text('bad')\nraise RuntimeError()\n"
    for name in ('sitecustomize.py','numpy.py','py3langid.py','worker.py'):
        (tmp_path/name).write_text(poison)
    fake=tmp_path/'specroad';fake.mkdir();(fake/'__init__.py').write_text(poison)
    before=inventory(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('PYTHONPATH',str(tmp_path))
    monkeypatch.setenv('PYTHONHOME',str(tmp_path))
    monkeypatch.setenv('LD_PRELOAD',str(tmp_path/'arbitrary.so'))
    value=request_value()
    value.pop('request_id');value.pop('snapshot_sha256');value.pop('contract_version')
    value['extensions']['example.launch']={'model_path':str(tmp_path/'worker.py'),
        'interpreter':'sh','worker':'worker.py','url':'https://untrusted.invalid'}
    request=create_request(**value)
    package=execute(request)
    assert package.request.canonical_bytes==request.canonical_bytes
    assert inventory(tmp_path)==before and not marker.exists()


@pytest.mark.parametrize('fault',['exit','malformed','extra_json','wrong_request','duplicate','launch'])
def test_worker_failures_are_concrete_and_never_successful_reports(monkeypatch,fault):
    request=AnalyzerRequest(encoded(request_value()))
    def run(command,**options):
        if fault=='launch':raise FileNotFoundError('no interpreter')
        raw=unavailable_package(request).canonical_bytes
        if fault=='malformed':raw=b'{'
        elif fault=='extra_json':raw+=b'\n{}'
        elif fault=='wrong_request':
            value=request_value();value['request_id']='different'
            raw=unavailable_package(AnalyzerRequest(encoded(value))).canonical_bytes
        elif fault=='duplicate':
            value=json.loads(raw)
            extra=unavailable_package(request).data['reports'][0]
            value['reports'].append(extra);raw=encoded(value)
        return subprocess.CompletedProcess(command,1 if fault=='exit' else 0,raw,b'diagnostic')
    monkeypatch.setattr('specroad.analyzers._worker_process.run_process',run)
    with pytest.raises(AnalyzerError) as caught:execute(request)
    assert caught.value.exit_code==5


@pytest.mark.parametrize('durable',[False,True])
def test_public_run_forwards_exact_data_in_both_paths(tmp_path,monkeypatch,durable):
    root=tmp_path/'project';project(root)
    request=call(['request','--analyzer',BUILTIN,'--analysis-id','explicit-worker'],root)
    raw=encoded(thaw(request.result));file=tmp_path/'request.json';file.write_bytes(raw)
    from specroad.analyzers._worker_process import run_process
    original=run_process;sent=[]
    def observe(command,**kwargs):
        sent.append(kwargs['input'])
        return original(command,**kwargs)
    monkeypatch.setattr('specroad.analyzers._worker_process.run_process',observe)
    if durable:
        from specroad import _build
        monkeypatch.setattr(_build,'BUILD_METADATA',dict(format_version=1,
            hash_algorithm='specroad-dev-payload-v1',build_sha256='a'*64))
    result=call(['run','--request',str(file)],tmp_path)
    assert result.exit_code==5
    assert sent==[AnalyzerRequest(raw).canonical_bytes]


@pytest.mark.parametrize('kind',['module','zipapp'])
def test_portable_core_runs_its_own_worker_without_optional_install(tmp_path,kind):
    module,archive=build_distribution(tmp_path/'distribution')
    request=AnalyzerRequest(encoded(request_value()))
    path=tmp_path/'request.json';path.write_bytes(request.canonical_bytes)
    result=run_python(['-I','-S','-B',str(module if kind=='module' else archive),
        'analyzer','run','--request',str(path),'--format','json'],tmp_path,capture=True)
    assert result.returncode==5,result.stderr
    value=json.loads(result.stdout)['result']
    # A sealed distribution returns the Work outcome's data envelope.
    package=ReportPackage(encoded(value.get('data',value)),request=request)
    assert package.request.canonical_bytes==request.canonical_bytes
    assert package.reports[0].data['run_status']=='unavailable'


def test_passive_commands_still_never_launch_worker(tmp_path):
    with patch('subprocess.Popen',side_effect=AssertionError('implicit worker')):
        assert call(['list'],tmp_path).exit_code==0
        assert call(['describe',BUILTIN],tmp_path).exit_code==0
