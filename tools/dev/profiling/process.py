"""Owned foreground subprocess groups, durable output and optional /proc samples."""
from contextlib import contextmanager
import os
import signal
import subprocess

from .common import encoded, write_json
from .resources import process_tree


@contextmanager
def interrupt_on_term():
    def interrupt(_signum, _frame):
        raise KeyboardInterrupt
    previous = signal.signal(signal.SIGTERM, interrupt)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def stop(process):
    # Only the group created for this command, never an existing profiling job.
    for sig, seconds in ((signal.SIGINT, 10), (signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            break
        try:
            process.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            continue
        # The launcher may have exited before its children. Escalate if the
        # original process group still exists; do not leave traced workers.
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            break
    process.wait()


def execute(command, root, environment, log, *, samples=None):
    with log.open('xb') as output:
        process = subprocess.Popen(command, cwd=root, env=environment,
                                   stdin=subprocess.DEVNULL, stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        stream = None
        try:
            write_json(log.with_suffix('.process.json'), dict(pid=process.pid, command=command))
            if samples is not None:
                stream = samples.open('x')
            while True:
                if stream is not None:
                    stream.write(encoded(process_tree(process.pid)) + '\n')
                    stream.flush()
                try:
                    return process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
        except BaseException:
            stop(process)
            raise
        finally:
            if stream is not None:
                stream.close()
