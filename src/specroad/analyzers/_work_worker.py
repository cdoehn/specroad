"""Private serial channel: one full request, one owned child, inert unit replies."""
from contextlib import ExitStack
import os
from pathlib import Path
import subprocess

from . import _worker_process
from ._worker_signals import WorkerCall, handled_worker_signals
from ._values import AnalyzerError, decode, encoded, require, shape
from ._work_values import (CHANNEL, check_engines, check_unit, static_engines,
                           select, unit_value)
from .reports import subject_result
from .registry import builtin_descriptor

BOOTSTRAP = ('import sys; sys.path.insert(0, sys.argv[1]); '
             'from specroad.analyzers._work_worker import main; raise SystemExit(main())')


class WorkWorker:
    """Lazily open a trusted worker; every exit owns cleanup and reaping."""
    def __init__(self):
        self.request = None
        self.rows = None
        self.child = None
        self.call = WorkerCall()
        self.stack = ExitStack()

    def __enter__(self):
        return self

    def __exit__(self, *error):
        self.call.child = None
        try:
            if self.child is not None:
                try:
                    if self.child.poll() is None:
                        self.child.kill()
                    self.child.wait()
                finally:
                    for stream in (self.child.stdin, self.child.stdout, self.child.stderr):
                        if stream is not None:
                            stream.close()
        finally:
            self.stack.close()
        if self.call.cancelled and error[0] is None:
            raise KeyboardInterrupt

    def _read(self):
        # All legal replies are bounded by the full owned request plus fixed
        # engine metadata. No project value can grow an unbounded reply stream.
        limit = 4 * len(self.request.canonical_bytes) + 1024 * 1024
        raw = self.child.stdout.readline(limit + 1)
        require(raw.endswith(b'\n') and len(raw) <= limit,
                'analyzer_worker_invalid_response', exit_code=5)
        return decode(raw)

    def _write(self, value):
        self.child.stdin.write(encoded(value) + b'\n')
        self.child.stdin.flush()

    def engines(self, request):
        if self.request is not None:
            require(self.request.canonical_bytes == request.canonical_bytes,
                    'analyzer_work_request_changed', exit_code=6)
            return decode(encoded({'engines': self.rows}))['engines']
        self.request = request
        if not any(e['descriptor'] == builtin_descriptor().data for e in request.data['analyzers']):
            self.rows = static_engines(request, 'external_result_only')
            return decode(encoded({'engines': self.rows}))['engines']
        distribution = _worker_process.distribution_path()
        interpreter = Path(_worker_process.sys.executable).absolute()
        require(interpreter.is_file(), 'analyzer_worker_interpreter_unavailable', exit_code=5)
        self.stack.enter_context(handled_worker_signals(self.call))
        try:
            self.child = subprocess.Popen([str(interpreter), '-I', '-S', '-B', '-c',
                BOOTSTRAP, str(distribution)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=None, cwd=distribution if distribution.is_dir() else distribution.parent,
                env={'PATH':os.defpath, 'LANG':'C.UTF-8', 'OPENBLAS_NUM_THREADS':'1', 'OMP_NUM_THREADS':'1'},
                start_new_session=(os.name == 'posix'), shell=False)
            self.call.child = self.child
            if self.call.cancelled:
                raise KeyboardInterrupt
            self._write(dict(channel=CHANNEL, request=request.data))
            reply = self._read()
            shape(reply, ('channel', 'binding', 'engines'))
            require(reply['channel'] == CHANNEL and reply['binding'] == request.binding,
                    'analyzer_worker_invalid_response', exit_code=5)
            check_engines(request, reply['engines'])
            self.rows = reply['engines']
            return decode(encoded({'engines': self.rows}))['engines']
        except (OSError, ValueError, AnalyzerError) as error:
            raise AnalyzerError('analyzer_worker_unavailable', exit_code=5) from error

    def subject(self, request, pair):
        rows = self.engines(request)
        entry, original = select(request, pair)
        if self.child is None:
            engine = next(row for row in rows if row['analyzer_id'] == entry['descriptor']['analyzer_id'])
            return unit_value(request, pair, engine, subject_result(original, status='open', payload={}), [])
        try:
            self._write(dict(channel=CHANNEL, binding=request.binding, pair=pair))
            return check_unit(request, pair, rows, self._read())
        except (OSError, ValueError, AnalyzerError) as error:
            raise AnalyzerError('analyzer_worker_invalid_response', exit_code=5) from error


def main():
    """Distribution-only entry; stdout is exclusively the closed work protocol."""
    import sys
    from .requests import AnalyzerRequest
    from ._work_engine import WorkEngine
    try:
        first = decode(sys.stdin.buffer.readline())
        shape(first, ('channel', 'request'))
        require(first['channel'] == CHANNEL, 'analyzer_work_channel', exit_code=2)
        request = AnalyzerRequest(encoded(first['request']))
        def emit(value):
            sys.stdout.buffer.write(encoded(value) + b'\n')
            sys.stdout.buffer.flush()
        with WorkEngine(request) as engine:
            emit(dict(channel=CHANNEL, binding=request.binding, engines=engine.rows))
            for raw in sys.stdin.buffer:
                command = decode(raw)
                shape(command, ('channel', 'binding', 'pair'))
                require(command['channel'] == CHANNEL and command['binding'] == request.binding,
                        'analyzer_work_request_changed', exit_code=6)
                emit(engine.subject(command['pair']))
    except (AnalyzerError, OSError, ValueError):
        sys.stderr.write('Analyzer work channel failed.\n')
        return 2
    return 0
