"""Real child ownership across repeated interruption and failed native cleanup."""

import errno
import json
import os
import signal
import subprocess

import pytest

from specroad.runtime.children import ChildCleanupError, run_child
from support.processes import run_core
from support.read_only import inventory
from test_owned_children import environment, python, reaped
from test_work_resume import recorded, setup


class Pipe:
    """Fault injection around an actual owned pipe, never a fake process."""
    def __init__(self, raw, close):
        self.raw, self.close = raw, close

    @property
    def closed(self):
        return self.raw.closed

    def __getattr__(self, name):
        return getattr(self.raw, name)


def running(monkeypatch, configure, *, primary=None):
    native = subprocess.Popen; processes = []; raw_pipes = []
    def launch(*args, **kwargs):
        process = native(*args, **kwargs); processes.append(process)
        raw_pipes.extend(p for p in (process.stdin, process.stdout, process.stderr) if p is not None)
        if primary is not None:
            def interrupted(*args, **kwargs):
                raise primary
            process.communicate = interrupted
        configure(process)
        return process
    monkeypatch.setattr(subprocess, 'Popen', launch)
    return native, processes, raw_pipes


def collect(native, processes, pipes):
    # The harness retains ownership when it deliberately prevents product cleanup.
    for process in processes:
        native.kill(process); native.wait(process)
    for stream in pipes:
        stream.close()


def blocked(tmp_path):
    return run_child(python('import signal,sys\nsys.stdin.buffer.read()\nsignal.pause()'),
        cwd=str(tmp_path), environment=environment(), input_bytes=b'owned input')


@pytest.mark.parametrize('operation', ['poll', 'kill', 'wait', 'stdin', 'stdout', 'stderr'])
@pytest.mark.parametrize('kind', ['keyboard', 'exit', 'eintr'])
def test_repeated_cleanup_interruptions_preserve_original_error_and_work(recorded, tmp_path, monkeypatch, operation, kind):
    initial, _, _, store = setup(tmp_path); before = inventory(tmp_path)
    primary = RuntimeError('owned call failure'); calls = []
    interruption = {'keyboard': KeyboardInterrupt(), 'exit': SystemExit(23),
                    'eintr': InterruptedError(errno.EINTR, 'owned interruption')}[kind]
    def configure(process):
        pipe = operation in ('stdin', 'stdout', 'stderr')
        target = getattr(process, operation)
        actual = target.close if pipe else target
        def action():
            calls.append(operation)
            if len(calls) <= 2:
                raise interruption
            return actual()
        setattr(process, operation, Pipe(target, action) if pipe else action)
    native, processes, pipes = running(monkeypatch, configure, primary=primary)
    try:
        with pytest.raises(RuntimeError) as caught:
            blocked(tmp_path)
        assert caught.value is primary and len(calls) >= 3
        assert processes[0].returncode == -signal.SIGKILL
        reaped(processes[0].pid)
        assert all(p.closed for p in pipes)
        assert inventory(tmp_path) == before and store.read().raw == initial.raw
    finally:
        collect(native, processes, pipes)


@pytest.mark.parametrize('kind', ['keyboard', 'exit', 'eintr'])
def test_late_interrupt_is_delivered_after_successful_child_collection(tmp_path, monkeypatch, kind):
    interruption = {'keyboard': KeyboardInterrupt(), 'exit': SystemExit(23),
                    'eintr': InterruptedError(errno.EINTR, 'owned interruption')}[kind]
    calls = []
    def configure(process):
        communicate, wait = process.communicate, process.wait
        def actual_communication(*args, **kwargs):
            result = communicate(*args, **kwargs)
            def late_wait():
                calls.append('wait')
                if len(calls) == 1: raise interruption
                return wait()
            process.wait = late_wait
            return result
        process.communicate = actual_communication
    native, processes, pipes = running(monkeypatch, configure)
    try:
        def invoke():
            return run_child(python("import sys\nsys.stdout.buffer.write(b'owned\\x00')"),
                             cwd=str(tmp_path), environment=environment())
        if kind == 'eintr':
            result = invoke(); assert result.returncode == 0 and result.stdout == b'owned\0'
        else:
            with pytest.raises(type(interruption)) as caught: invoke()
            assert caught.value is interruption
        assert calls == ['wait', 'wait'] and processes[0].returncode == 0
        reaped(processes[0].pid); assert all(p.closed for p in pipes)
    finally:
        collect(native, processes, pipes)


@pytest.mark.parametrize('channel', ['stdin', 'stdout', 'stderr', 'all'])
@pytest.mark.parametrize('late', [False, True])
def test_every_pipe_is_attempted_and_actual_cleanup_failure_is_reported(recorded, tmp_path, monkeypatch, channel, late):
    initial, _, _, store = setup(tmp_path); before = inventory(tmp_path)
    primary = RuntimeError('owned communication failure'); called = []
    selected = ['stdin', 'stdout', 'stderr'] if channel == 'all' else [channel]
    def configure(process):
        for name in ('stdin', 'stdout', 'stderr'):
            raw = getattr(process, name)
            def close(name=name, raw=raw):
                called.append(name)
                if name in selected:
                    if late: raw.close()
                    raise OSError(errno.EIO, 'owned close failure')
                raw.close()
            setattr(process, name, Pipe(raw, close))
    native, processes, pipes = running(monkeypatch, configure, primary=primary)
    try:
        with pytest.raises(ChildCleanupError) as caught: blocked(tmp_path)
        error = caught.value; value = error.as_dict()
        assert error.__cause__ is primary and called == ['stdin', 'stdout', 'stderr']
        assert value == {'reason': 'child_cleanup_incomplete', 'exit_code': 5,
            'pid': processes[0].pid, 'returncode': -signal.SIGKILL, 'child_reaped': True,
            'open_pipes': [] if late else selected, 'interrupted': False,
            'failures': [{'operation': 'close_' + name, 'error_type': 'OSError'} for name in selected]}
        value['failures'].clear(); value['open_pipes'].clear()
        assert len(error.as_dict()['failures']) == len(selected)
        reaped(processes[0].pid)
        assert inventory(tmp_path) == before and store.read().raw == initial.raw
    finally:
        collect(native, processes, pipes)


def test_failed_kill_reports_a_live_child_without_waiting_or_claiming_completion(recorded, tmp_path, monkeypatch):
    initial, _, _, store = setup(tmp_path); before = inventory(tmp_path)
    primary = RuntimeError('owned communication failure'); calls = []
    def configure(process):
        def denied():
            calls.append('kill'); raise PermissionError(errno.EPERM, 'owned denial')
        def must_not_wait():
            raise AssertionError('Blocking wait after a failed kill')
        process.kill, process.wait = denied, must_not_wait
    native, processes, pipes = running(monkeypatch, configure, primary=primary)
    try:
        with pytest.raises(ChildCleanupError) as caught: blocked(tmp_path)
        value = caught.value.as_dict()
        assert caught.value.__cause__ is primary and calls == ['kill']
        assert value['child_reaped'] is False and value['returncode'] is None and value['open_pipes'] == []
        assert value['failures'] == [{'operation': 'kill', 'error_type': 'PermissionError'}]
        assert processes[0].poll() is None
        assert inventory(tmp_path) == before and store.read().raw == initial.raw
    finally:
        collect(native, processes, pipes)


def test_failure_after_native_wait_retains_the_observed_reaped_state(recorded, tmp_path, monkeypatch):
    initial, _, _, store = setup(tmp_path); before = inventory(tmp_path)
    primary = RuntimeError('owned communication failure')
    def configure(process):
        wait = process.wait
        def failed():
            wait(); raise OSError(errno.EIO, 'owned late wait failure')
        process.wait = failed
    native, processes, pipes = running(monkeypatch, configure, primary=primary)
    try:
        with pytest.raises(ChildCleanupError) as caught: blocked(tmp_path)
        value = caught.value.as_dict()
        assert caught.value.__cause__ is primary and value['child_reaped'] is True
        assert value['returncode'] == -signal.SIGKILL and value['open_pipes'] == []
        assert value['failures'] == [{'operation': 'wait', 'error_type': 'OSError'}]
        reaped(processes[0].pid)
        assert inventory(tmp_path) == before and store.read().raw == initial.raw
    finally:
        collect(native, processes, pipes)


@pytest.mark.parametrize('exit_handler', [False, True])
def test_real_handled_sigterm_reaps_the_child_and_preserves_the_checkpoint(recorded, tmp_path, exit_handler):
    initial, roots, location, store = setup(tmp_path)
    work_before = inventory(location.path); project_before = inventory(roots[0].root)
    run = tmp_path / 'run'; run.mkdir()
    child = ("import os,signal,sys\nfrom pathlib import Path\n"
        "signal.signal(signal.SIGTERM,signal.SIG_IGN)\nsys.stdin.buffer.read()\n"
        "Path('pid').write_text(str(os.getpid()))\nos.kill(os.getppid(),signal.SIGTERM)\nsignal.pause()\n")
    exception = 'SystemExit(23)' if exit_handler else "RuntimeError('owned stop')"
    body = ("import json,os,signal,sys\nfrom pathlib import Path\n"
        "from specroad.runtime.children import run_child\n"
        "def stop(signum,frame):raise " + exception + "\n"
        "signal.signal(signal.SIGTERM,stop)\nenv={'PATH':''}\n"
        "if 'LD_LIBRARY_PATH' in os.environ:env['LD_LIBRARY_PATH']=os.environ['LD_LIBRARY_PATH']\n"
        "try:\n run_child((sys.executable,'-I','-S','-B','-c'," + repr(child) + "),cwd=os.getcwd(),environment=env,input_bytes=b'go')\n"
        "except (RuntimeError,SystemExit) as error:\n"
        " pid=int(Path('pid').read_text())\n"
        " try:os.waitpid(pid,os.WNOHANG)\n"
        " except ChildProcessError:print(json.dumps({'reaped':True,'kind':type(error).__name__}))\n"
        " else:raise AssertionError('Child was not reaped')\n"
        "else:raise AssertionError('Expected actual termination signal')\n")
    completed = run_core(body, run, capture=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {'reaped': True, 'kind': 'SystemExit' if exit_handler else 'RuntimeError'}
    assert inventory(location.path) == work_before and inventory(roots[0].root) == project_before
    assert store.read().raw == initial.raw


def test_error_after_actual_child_exit_does_not_send_an_unnecessary_signal(tmp_path, monkeypatch):
    primary = RuntimeError('owned late result failure')
    def configure(process):
        communicate = process.communicate
        def completed(*args, **kwargs):
            communicate(*args, **kwargs)
            def forbidden(): raise AssertionError('Exited child was signalled')
            process.kill = forbidden
            raise primary
        process.communicate = completed
    native, processes, pipes = running(monkeypatch, configure)
    try:
        with pytest.raises(RuntimeError) as caught:
            run_child(python('pass'), cwd=str(tmp_path), environment=environment())
        assert caught.value is primary and processes[0].returncode == 0
        reaped(processes[0].pid); assert all(p.closed for p in pipes)
    finally:
        collect(native, processes, pipes)


def test_child_closing_input_early_keeps_its_actual_status_and_output(tmp_path):
    body = "import os,sys\nraw=sys.stdin.buffer.read(1)\nprint(os.getpid(),flush=True)\nsys.stderr.buffer.write(raw)\nraise SystemExit(17)"
    result = run_child(python(body), cwd=str(tmp_path), environment=environment(), input_bytes=b'x' * (4 * 1024 * 1024))
    assert result.returncode == 17 and result.stderr == b'x'
    reaped(int(result.stdout))
