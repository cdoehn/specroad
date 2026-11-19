"""Real known worker transport; no classifier success before its planned engine."""
from pathlib import Path
from unittest.mock import patch

from specroad.analyzers.worker_transport import execute, invoke_worker
from specroad.analyzers.requests import AnalyzerRequest
from specroad.analyzers._values import encoded
from specroad.analyzers.requests import create_request, analyzer_binding
from specroad.analyzers.registry import builtin_descriptor
from test_analyzer_requests import inputs


def request_value():
    value=inputs()
    value['analyzers']=[analyzer_binding(builtin_descriptor(),['language_detection'])]
    value['settings']={'specroad.py3langid':{}}
    return create_request(**value,analysis_id='worker-request').data


def test_full_bound_request_reaches_real_worker():
    request = AnalyzerRequest(encoded(request_value()))
    package = invoke_worker(request)
    assert package.request.canonical_bytes == request.canonical_bytes
    assert len(package.reports) == len(request.data['analyzers'])
    for report in package.reports:
        assert report.data['run_status'] == 'unavailable'
        assert report.data['coverage']['counts']['open'] == len(request.data['subjects'])
        assert report.data['operational']['execution_supported'] is False


def test_launch_has_explicit_interpreter_and_no_shell(monkeypatch):
    import subprocess
    from specroad.analyzers._execution import unavailable_package
    request=AnalyzerRequest(encoded(request_value()))
    observed={}
    def run(command, **options):
        observed.update(command=command,options=options)
        assert options['input']==request.canonical_bytes
        assert options['shell'] is False and Path(command[0]).is_absolute()
        assert command[1:4]==['-I','-S','-B']
        assert Path(options['cwd']).is_dir()
        return subprocess.CompletedProcess(command,0,unavailable_package(request).canonical_bytes,b'')
    monkeypatch.setattr('specroad.analyzers._worker_process.run_process',run)
    execute(request)
    assert Path(observed['options']['cwd']).is_absolute()


def test_foreign_descriptor_never_selects_a_process():
    request=create_request(**inputs(),analysis_id='external-only')
    with patch('subprocess.Popen',side_effect=AssertionError('foreign process')):
        package=execute(request)
    assert package.reports[0].data['run_status']=='unavailable'
