"""Real direct children finish or are killed/reaped; Work bytes stay owned.

Child programs and their executable are explicitly trusted test-host fixtures.
Signal tests isolate the parent from pytest and synchronize through actual stdin.
"""

import _thread
import builtins
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading

import pytest

from specroad.runtime.children import ChildContractError, run_child
from specroad.work.finalization import finalize_read_only_work
from specroad.work.packages import export_work_package
from specroad.work.resume import resume_read_only_work
from support.processes import run_core
from support.read_only import inventory, no_write_attempts
from test_work_packages import restore
from test_work_publication import setup as native_setup, ready, publish
from test_work_resume import recorded, setup


def environment():
    # Same explicitly named loader input as the isolated test-process harness.
    result = {'PATH': ''}
    if 'LD_LIBRARY_PATH' in os.environ:
        result['LD_LIBRARY_PATH'] = os.environ['LD_LIBRARY_PATH']
    return result


def python(body, *arguments):
    return (sys.executable, '-I', '-S', '-B', '-c', body, *arguments)


def reaped(pid):
    with pytest.raises(builtins.ChildProcessError):
        os.waitpid(pid, os.WNOHANG)


@pytest.mark.parametrize('exit_code', [0, 17])
def test_actual_binary_streams_and_nonzero_status_are_preserved(tmp_path, exit_code):
    data = bytes(range(256)) * 4096
    body = ("import os,sys\nfrom pathlib import Path\n"
        "Path('pid').write_text(str(os.getpid()))\n"
        "raw=sys.stdin.buffer.read()\nsys.stdout.buffer.write(raw[::-1])\n"
        "sys.stderr.buffer.write(raw+ b'\\x00error')\nraise SystemExit(" + str(exit_code) + ')\n')
    result = run_child(python(body), cwd=str(tmp_path), environment=environment(), input_bytes=data)
    assert result.returncode == exit_code and result.stdout == data[::-1]
    assert result.stderr == data + b'\0error'
    pid = int((tmp_path / 'pid').read_text())
    reaped(pid)


def test_explicit_environment_closed_stdin_and_literal_arguments(tmp_path, monkeypatch):
    monkeypatch.setenv('SPECRD_TEST_SECRET', 'owned-not-for-child')
    cwd = tmp_path / 'trusted cwd; literal'; cwd.mkdir()
    arguments = ('$(touch SHOULD_NOT_EXIST)', '; touch ALSO_NOT_CREATED', 'space argument', '')
    body = ("import os,sys,json\nprint(json.dumps({'pid':os.getpid(),'cwd':os.getcwd(),"
        "'stdin':sys.stdin.read(),'args':sys.argv[1:],'secret':os.environ.get('SPECRD_TEST_SECRET'),"
        "'path':os.environ.get('PATH'),'named':os.environ.get('OWNED_INPUT')}))")
    options = {**environment(), 'OWNED_INPUT': 'explicit value'}
    before = inventory(tmp_path)
    result = run_child(python(body, *arguments), cwd=str(cwd), environment=options)
    value = json.loads(result.stdout)
    assert result.returncode == 0 and not result.stderr
    assert value['cwd'] == str(cwd) and value['stdin'] == '' and value['args'] == list(arguments)
    assert value['secret'] is None and value['path'] == '' and value['named'] == 'explicit value'
    assert inventory(tmp_path) == before and options['OWNED_INPUT'] == 'explicit value'
    reaped(value['pid'])


def test_parent_descriptors_do_not_cross_into_the_child(tmp_path):
    source = tmp_path / 'owned'; source.write_bytes(b'private parent descriptor')
    with source.open('rb') as stream:
        fd = fcntl.fcntl(stream.fileno(), fcntl.F_DUPFD, 100)
        os.set_inheritable(fd, True)
        try:
            body = ("import os,sys\ntry:os.fstat(int(sys.argv[1]))\n"
                "except OSError:raise SystemExit(0)\nelse:raise SystemExit(19)\n")
            result = run_child(python(body, str(fd)), cwd=str(tmp_path), environment=environment())
            assert result.returncode == 0 and not result.stdout and not result.stderr
            assert os.read(fd, 100) == b'private parent descriptor'
        finally:
            os.close(fd)


def test_native_signal_exit_is_not_changed_to_success(tmp_path):
    body = "import os,signal\nprint(os.getpid(),flush=True)\nos.kill(os.getpid(),signal.SIGTERM)\n"
    result = run_child(python(body), cwd=str(tmp_path), environment=environment())
    assert result.returncode == -signal.SIGTERM
    reaped(int(result.stdout))


@pytest.mark.parametrize('change', [
    {'arguments': 'python -c pass'}, {'arguments': []}, {'arguments': ()},
    {'arguments': ('relative-python',)}, {'arguments': (sys.executable, b'bytes')},
    {'arguments': (sys.executable, 'a\0b')}, {'cwd': 'relative'}, {'cwd': None},
    {'environment': None}, {'environment': {'': 'value'}}, {'environment': {'A=B': 'value'}},
    {'environment': {'KEY': None}}, {'environment': {'KEY': 'a\0b'}}, {'input_bytes': 'text'},
])
def test_invalid_contracts_are_rejected_before_process_or_file_effects(tmp_path, change):
    options = {'arguments': python('pass'), 'cwd': str(tmp_path), 'environment': environment(),
               'input_bytes': None, **change}
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ChildContractError) as caught:
        run_child(**options)
    assert caught.value.as_dict() == {'reason': 'invalid_child_contract', 'exit_code': 2}
    assert inventory(tmp_path) == before


def test_native_launch_failure_is_preserved_without_retry_or_work_cleanup(recorded, tmp_path, monkeypatch):
    initial, _, _, store = setup(tmp_path); before = inventory(tmp_path)
    original = subprocess.Popen; calls = []
    def launch(*args, **kwargs):
        calls.append(args[0]); return original(*args, **kwargs)
    monkeypatch.setattr(subprocess, 'Popen', launch)
    with pytest.raises(FileNotFoundError):
        run_child((str(tmp_path / 'not-installed'),), cwd=str(tmp_path), environment=environment())
    assert len(calls) == 1 and inventory(tmp_path) == before and store.read().raw == initial.raw


@pytest.mark.parametrize('error', [RuntimeError('owned failure'), KeyboardInterrupt(), SystemExit(23)])
def test_handled_exception_kills_and_reaps_the_actual_child_and_retains_work(recorded, tmp_path, monkeypatch, error):
    initial, _, _, store = setup(tmp_path); before = inventory(tmp_path)
    original = subprocess.Popen; processes = []
    def launch(*args, **kwargs):
        process = original(*args, **kwargs); processes.append(process); return process
    def abort(self, *args, **kwargs):
        raise error
    monkeypatch.setattr(original, 'communicate', abort)
    monkeypatch.setattr(subprocess, 'Popen', launch)
    with pytest.raises(type(error)) as caught:
        run_child(python('import sys\nsys.stdin.buffer.read()'), cwd=str(tmp_path),
                  environment=environment(), input_bytes=b'owned input')
    assert caught.value is error and len(processes) == 1
    process = processes[0]
    assert process.returncode == -signal.SIGKILL
    reaped(process.pid)
    assert all(stream.closed for stream in (process.stdin, process.stdout, process.stderr))
    assert inventory(tmp_path) == before and store.read().raw == initial.raw


def test_real_keyboard_interrupt_of_an_isolated_parent_reaps_an_ignoring_child(tmp_path):
    child = ("import os,signal,sys\nfrom pathlib import Path\n"
        "signal.signal(signal.SIGINT,signal.SIG_IGN)\nsys.stdin.buffer.read()\n"
        "Path('pid').write_text(str(os.getpid()))\nos.kill(os.getppid(),signal.SIGINT)\nsignal.pause()\n")
    body = ("import json,os,sys\nfrom pathlib import Path\n"
        "from specroad.runtime.children import run_child\n"
        "env={'PATH':''}\n"
        "if 'LD_LIBRARY_PATH' in os.environ:env['LD_LIBRARY_PATH']=os.environ['LD_LIBRARY_PATH']\n"
        "try:\n run_child((sys.executable,'-I','-S','-B','-c'," + repr(child) + "),cwd=os.getcwd(),environment=env,input_bytes=b'go')\n"
        "except KeyboardInterrupt:\n"
        " pid=int(Path('pid').read_text())\n"
        " try:os.waitpid(pid,os.WNOHANG)\n"
        " except ChildProcessError:print(json.dumps({'cancelled':True,'reaped':True}))\n"
        " else:raise AssertionError('Child was not reaped')\n"
        "else:raise AssertionError('Expected actual interruption')\n")
    completed = run_core(body, tmp_path, capture=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {'cancelled': True, 'reaped': True}


def test_each_explicit_call_owns_one_child_without_background_threads(tmp_path, monkeypatch):
    original = subprocess.Popen; processes = []
    def launch(*args, **kwargs):
        assert all(p.returncode is not None for p in processes)
        process = original(*args, **kwargs); processes.append(process); return process
    def forbidden(*args, **kwargs):
        raise AssertionError('A background thread was started')
    monkeypatch.setattr(subprocess, 'Popen', launch)
    monkeypatch.setattr(threading.Thread, 'start', forbidden)
    monkeypatch.setattr(_thread, 'start_new_thread', forbidden)
    for _ in range(2):
        result = run_child(python('import os\nprint(os.getpid())'), cwd=str(tmp_path), environment=environment())
        assert result.returncode == 0 and int(result.stdout) == processes[-1].pid
        assert processes[-1].stdout.closed and processes[-1].stderr.closed
        reaped(processes[-1].pid)
    assert len(processes) == 2


@pytest.mark.parametrize('kind', ['read_only', 'native'])
def test_current_work_flows_start_no_pool_watcher_or_helper_process(recorded, tmp_path, monkeypatch, kind):
    if kind == 'read_only': initial, roots, _, store = setup(tmp_path)
    else: model, plan, _, registry, _, _, store = native_setup(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError('Core started an unrequested background worker')
    with monkeypatch.context() as patcher:
        patcher.setattr(subprocess, 'Popen', forbidden)
        patcher.setattr(threading.Thread, 'start', forbidden)
        patcher.setattr(_thread, 'start_new_thread', forbidden)
        for name in ('fork', 'forkpty', 'posix_spawn', 'posix_spawnp', 'system'):
            if hasattr(os, name): patcher.setattr(os, name, forbidden)
        if kind == 'read_only':
            assert resume_read_only_work(store).executed
            finalize_read_only_work(store)
            rebuilt = restore(export_work_package(store), roots, tmp_path / 'restored')
            assert rebuilt.read().raw == store.read().raw and rebuilt.read().as_dict()['state'] == 'completed'
        else:
            ready(store, registry, model, plan)
            result = publish(store, registry, model, plan).as_dict()
            assert result['publication_performed'] and result['transaction']['cleanup_completed']
