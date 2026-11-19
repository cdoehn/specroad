"""Narrow trusted process boundary, separate from analyzer route selection."""
import os
from contextlib import contextmanager
from pathlib import Path
import signal
import subprocess
import sys
import threading
import zipimport

from ._values import AnalyzerError, require
from .packages import ReportPackage
from .requests import AnalyzerRequest

BOOTSTRAP = ('import sys; sys.path.insert(0, sys.argv[1]); '
             'from specroad.analyzers.worker import main; raise SystemExit(main())')


class WorkerCall:
    """Defer handled launch interruption until the child has a known owner."""

    def __init__(self):
        self.child = None
        self.cancelled = False

    def interrupt(self, signum, frame):
        self.cancelled = True
        if self.child is not None:
            raise KeyboardInterrupt


@contextmanager
def handled_worker_signals(call):
    """Restore caller handlers and keep launch interruption recoverable.

    A signal before Popen returns is recorded without raising across process
    creation. No promise is made for SIGKILL or loss of the whole host.
    """
    previous = {}
    try:
        if threading.current_thread() is threading.main_thread():
            for signum in (signal.SIGINT, signal.SIGTERM, getattr(signal, 'SIGHUP', None)):
                if signum is not None:
                    previous[signum] = signal.getsignal(signum)
                    signal.signal(signum, call.interrupt)
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def run_process(command, *, input, check=False, **options):
    """Own, stop and reap the one child through every handled exit path."""
    require(check is False, 'analyzer_worker_check_option', exit_code=2)
    call = WorkerCall()
    with handled_worker_signals(call):
        child = subprocess.Popen(command, **options)
        # From creation until this try is entered, the handler only records
        # cancellation. There is no unowned-child window that can raise.
        try:
            call.child = child
            if call.cancelled:
                raise KeyboardInterrupt
            stdout, stderr = child.communicate(input)
        finally:
            # Further handled signals during cleanup are recorded, not raised.
            call.child = None
            try:
                if child.poll() is None:
                    child.kill()
                child.wait()
            finally:
                for stream in (child.stdin, child.stdout, child.stderr):
                    if stream is not None:
                        stream.close()
        if call.cancelled:
            raise KeyboardInterrupt
    return subprocess.CompletedProcess(command, child.returncode, stdout, stderr)


def distribution_path():
    import specroad
    loader = specroad.__loader__
    if isinstance(loader, zipimport.zipimporter):
        return Path(loader.archive).resolve(strict=True)
    return Path(specroad.__file__).resolve(strict=True).parent.parent


def invoke_worker(request):
    require(type(request) is AnalyzerRequest, 'analyzer_request_required', exit_code=2)
    interpreter = Path(sys.executable).absolute()
    require(interpreter.is_file(), 'analyzer_worker_interpreter_unavailable', exit_code=5)
    distribution = distribution_path()
    command = [str(interpreter), '-I', '-S', '-B', '-c', BOOTSTRAP, str(distribution)]
    try:
        completed = run_process(command, input=request.canonical_bytes,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=distribution if distribution.is_dir() else distribution.parent,
            env={'PATH':os.defpath, 'LANG':'C.UTF-8',
                 'OPENBLAS_NUM_THREADS':'1', 'OMP_NUM_THREADS':'1'},
            start_new_session=(os.name == 'posix'), shell=False, check=False)
        require(completed.returncode == 0, 'analyzer_worker_failed', exit_code=5)
        try:
            package = ReportPackage(completed.stdout, request=request)
            names = [r.data['analyzer']['descriptor']['analyzer_id'] for r in package.reports]
            require(len(names) == len(set(names)) == len(request.data['analyzers']),
                    'analyzer_worker_duplicate_analyzer')
        except AnalyzerError as error:
            raise AnalyzerError('analyzer_worker_invalid_response', exit_code=5) from error
        return package
    except OSError as error:
        raise AnalyzerError('analyzer_worker_unavailable', exit_code=5) from error
