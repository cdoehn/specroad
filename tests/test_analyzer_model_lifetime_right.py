"""Real child cleanup and offline boundaries; all children belong to each case."""
import gc
import os
import signal
import subprocess
import sys
from types import ModuleType
from unittest.mock import patch
import weakref

import pytest

from specroad.analyzers import _model_session, _worker_process
from specroad.analyzers._model_session import ModelSession
from specroad.analyzers._values import AnalyzerError, encoded
from specroad.analyzers.requests import AnalyzerRequest, create_request
from specroad.analyzers.worker import run_request
from test_analyzer_model_lifetime import OwnedModel
from test_analyzer_worker import request_value


@pytest.mark.parametrize('failure', [KeyboardInterrupt, SystemExit, ValueError])
def test_model_owner_releases_on_every_handled_exception(monkeypatch, failure):
    living = []
    def load():
        model = OwnedModel(); living.append(weakref.ref(model)); return model
    monkeypatch.setattr(_model_session, 'load_reference_model', load)
    with pytest.raises(failure):
        with ModelSession() as session:
            session.model()
            raise failure()
    gc.collect()
    assert living[0]() is None
    session.close()  # Closing twice cannot reinitialize a model.
    with pytest.raises(AnalyzerError):
        session.__enter__()


@pytest.mark.parametrize('outcome', ['normal', 'exit', 'interrupt', 'terminate', 'terminate_during_spawn', 'io_error', 'system_exit'])
def test_actual_worker_is_reaped_on_completion_error_and_handled_abort(tmp_path, monkeypatch, outcome):
    request = AnalyzerRequest(encoded(request_value()))
    children = []
    previous = {s:signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
    original = subprocess.Popen
    if outcome == 'exit':
        monkeypatch.setattr(_worker_process, 'BOOTSTRAP', 'raise SystemExit(2)')
    elif outcome not in ('normal',):
        # A real owned child acknowledges startup, then waits on its stdin.
        # The parent raises/handles the chosen failure only after this handshake.
        monkeypatch.setattr(_worker_process, 'BOOTSTRAP',
            "import sys; print('ready', flush=True); sys.stdin.buffer.read()")
    def launch(*args, **kwargs):
        child = original(*args, **kwargs); children.append(child)
        if outcome == 'terminate_during_spawn':
            signal.raise_signal(signal.SIGTERM)
        if outcome not in ('normal', 'exit', 'terminate_during_spawn'):
            communicate = child.communicate
            def fail_after_ready(*arguments, **options):
                assert child.stdout.readline() == b'ready\n'
                child.communicate = communicate
                if outcome == 'terminate': signal.raise_signal(signal.SIGTERM)
                if outcome == 'io_error': raise OSError('IPC failure')
                if outcome == 'system_exit': raise SystemExit(3)
                raise KeyboardInterrupt
            child.communicate = fail_after_ready
        return child
    monkeypatch.setattr(subprocess, 'Popen', launch)
    try:
        if outcome == 'normal':
            result = _worker_process.invoke_worker(request)
            assert result.request.canonical_bytes == request.canonical_bytes
        else:
            expected = (AnalyzerError if outcome in ('exit', 'io_error') else
                        SystemExit if outcome == 'system_exit' else KeyboardInterrupt)
            with pytest.raises(expected):
                _worker_process.invoke_worker(request)
        assert len(children) == 1 and children[0].returncode is not None
        assert children[0].poll() is not None
        if os.name == 'posix':
            with pytest.raises(ChildProcessError):
                os.waitpid(children[0].pid, os.WNOHANG)
        assert {s:signal.getsignal(s) for s in previous} == previous
    finally:
        # Failure of the oracle must not leave a fixture's child running.
        for child in children:
            if child.poll() is None: child.kill()
            child.wait()


def test_failed_spawn_restores_callers_signal_handlers(monkeypatch):
    before = {s:signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
    with patch('subprocess.Popen', side_effect=OSError('cannot start')):
        with pytest.raises(AnalyzerError) as caught:
            _worker_process.invoke_worker(AnalyzerRequest(encoded(request_value())))
    assert caught.value.exit_code == 5
    assert {s:signal.getsignal(s) for s in before} == before


@pytest.mark.parametrize('fault', ['hash', 'missing', 'directory', 'symlink', 'fifo', 'version'])
def test_untrusted_or_unavailable_model_is_not_decoded(tmp_path, monkeypatch, fault):
    package = tmp_path / 'py3langid'; package.mkdir()
    init = package / '__init__.py'; init.write_bytes(b'')
    data = package / 'data'; data.mkdir()
    model = data / 'model.npz.xz'
    if fault == 'directory': model.mkdir()
    elif fault == 'symlink':
        target = tmp_path / 'foreign'; target.write_bytes(b'foreign')
        model.symlink_to(target)
    elif fault == 'fifo': os.mkfifo(model)
    elif fault != 'missing': model.write_bytes(b'not the shipped model')
    library = ModuleType('py3langid')
    library.__file__ = str(init); library.__version__ = '0.3.0' if fault == 'version' else '0.4.0'
    backend = ModuleType('py3langid.langid')
    storage = ModuleType('py3langid.modelio')
    def forbidden(*args, **kwargs): raise AssertionError('unverified model decoded')
    backend.LanguageIdentifier = forbidden; storage.load_model = forbidden
    for name, value in [('py3langid', library), ('py3langid.langid', backend), ('py3langid.modelio', storage)]:
        monkeypatch.setitem(sys.modules, name, value)
    with ModelSession() as session:
        with pytest.raises(AnalyzerError) as caught: session.model()
        assert caught.value.exit_code == 5


def test_project_options_never_select_upstream_modes_or_installers(monkeypatch):
    value = request_value()
    for key in ('contract_version', 'request_id', 'snapshot_sha256'): value.pop(key)
    value['extensions']['example.untrusted'] = {
        'url':'https://untrusted.invalid', 'train':True, 'serve':True, 'telemetry':True,
        'install':'pip install evil', 'model':'/project/foreign.model', 'background':True}
    request = create_request(**value)
    calls = []
    def load(): calls.append(1); return OwnedModel()
    monkeypatch.setattr(_model_session, 'load_reference_model', load)
    with (patch('socket.socket', side_effect=AssertionError('network')),
          patch('subprocess.Popen', side_effect=AssertionError('subprocess mode'))):
        package = run_request(request)
    assert calls == [1] and package.request.canonical_bytes == request.canonical_bytes


def test_worker_does_not_inherit_numeric_background_threads(monkeypatch):
    request = AnalyzerRequest(encoded(request_value()))
    from specroad.analyzers._execution import unavailable_package
    monkeypatch.setenv('OPENBLAS_NUM_THREADS', '64')
    monkeypatch.setenv('OMP_NUM_THREADS', '64')
    observed = []
    def run(command, **options):
        observed.append(options)
        return subprocess.CompletedProcess(command, 0, unavailable_package(request).canonical_bytes, b'')
    monkeypatch.setattr(_worker_process, 'run_process', run)
    _worker_process.invoke_worker(request)
    assert observed[0]['env'] == {'PATH':os.defpath, 'LANG':'C.UTF-8',
                                  'OPENBLAS_NUM_THREADS':'1', 'OMP_NUM_THREADS':'1'}
    assert observed[0]['start_new_session'] is (os.name == 'posix')
