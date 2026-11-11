"""Optional low-scope test-body line events on CPython with sys.monitoring."""
import inspect
import sys
import threading
import time

from .common import encoded, write_json


class LineTrace:
    def __init__(self, item, directory):
        self.monitoring = getattr(sys, 'monitoring', None)
        self.tool = None
        self.stream = None
        self.code = getattr(inspect.unwrap(getattr(item, 'obj', None)), '__code__', None)
        available = next((i for i in (5, 4, 3) if self.monitoring.get_tool(i) is None), None) if self.monitoring else None
        metadata = dict(available=False, nodeid=item.nodeid,
                        scope='test function only; Python 3.12+; cProfile remains separate')
        if available is not None and self.code is not None:
            try:
                self.monitoring.use_tool_id(available, 'specroad-test-profile-lines')
                self.tool = available
                self.stream = (directory / 'lines.jsonl').open('x')
                self.monitoring.register_callback(self.tool, self.monitoring.events.LINE, self.line)
                self.monitoring.register_callback(self.tool, self.monitoring.events.PY_RETURN, self.returned)
                self.monitoring.set_local_events(self.tool, self.code,
                    self.monitoring.events.LINE | self.monitoring.events.PY_RETURN)
                metadata.update(available=True, filename=self.code.co_filename,
                                first_line=self.code.co_firstlineno, function=self.code.co_name)
            except BaseException:
                self.close()
                raise
        try:
            write_json(directory / 'line-trace.json', metadata)
        except BaseException:
            self.close()
            raise

    def emit(self, **value):
        self.stream.write(encoded(dict(time_ns=time.time_ns(), cpu_ns=time.process_time_ns(),
                                       tid=threading.get_native_id(), **value)) + '\n')
        self.stream.flush()

    def line(self, code, number):
        self.emit(event='line', line=number)

    def returned(self, code, offset, value):
        self.emit(event='return', offset=offset)

    def close(self):
        try:
            if self.tool is not None:
                self.monitoring.set_local_events(self.tool, self.code, 0)
                self.monitoring.set_events(self.tool, 0)
                self.monitoring.register_callback(self.tool, self.monitoring.events.LINE, None)
                self.monitoring.register_callback(self.tool, self.monitoring.events.PY_RETURN, None)
                self.monitoring.free_tool_id(self.tool)
                self.tool = None
        finally:
            if self.stream is not None:
                self.stream.close()
                self.stream = None
