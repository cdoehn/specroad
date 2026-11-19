"""Single owner and guaranteed cleanup for a trusted worker process."""
from contextlib import contextmanager
import signal
import subprocess
import threading
from ._values import require


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
