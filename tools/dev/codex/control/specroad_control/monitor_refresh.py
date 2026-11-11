"""Bounded independent collectors, separate from CLI and terminal rendering."""
from copy import deepcopy
import queue
import threading
import time
from .monitor_data import collect


class Refresh:
    def __init__(self, paths, *, collector=collect, interval=5.0, timeout=5.0, clock=time.monotonic):
        self.paths = list(paths)
        self.collector, self.interval, self.timeout, self.clock = collector, interval, timeout, clock
        self.messages = queue.Queue(maxsize=max(1, len(self.paths)))
        self.pending, self.due, self.rows = {}, {}, {}
        self.closed = False
        for path in self.paths:
            self.rows[path.instance] = {'instance': path.instance, 'state': None, 'source': None,
                'stale': True, 'worker_reachable': False, 'refreshing': False, 'errors': {}}

    def _read(self, path):
        try:
            value = self.collector(path)
        except Exception as exc:
            value = {'instance': path.instance, 'state': None, 'source': None, 'stale': True,
                     'worker_reachable': False, 'errors': {'collector': getattr(exc, 'code', type(exc).__name__)}}
        self.messages.put((path.instance, value))

    def poll(self, *, force=False):
        if self.closed:
            return
        now = self.clock()
        while True:
            try:
                name, value = self.messages.get_nowait()
            except queue.Empty:
                break
            started = self.pending.pop(name, now)
            if now - started > self.timeout:
                value = dict(value, stale=True, worker_reachable=False,
                             errors=dict(value.get('errors', {}), refresh='deadline_exceeded'))
            self.rows[name] = dict(value, refreshing=False)
            self.due[name] = now + self.interval
        for path in self.paths:
            name = path.instance
            if name in self.pending:
                if now - self.pending[name] >= self.timeout:
                    self.rows[name].update(stale=True, worker_reachable=False, refreshing=True)
                    self.rows[name]['errors'] = dict(self.rows[name].get('errors', {}), refresh='timeout')
                continue  # No second thread while a slow source still owns its slot.
            if force or now >= self.due.get(name, 0):
                self.pending[name] = now
                self.rows[name]['refreshing'] = True
                threading.Thread(target=self._read, args=(path,), daemon=True,
                                 name='control-monitor-' + name).start()

    def snapshot(self):
        return {'format_version': 1, 'kind': 'specroad-control-monitor', 'observed_at': time.time(),
                'instances': [deepcopy(self.rows[path.instance]) for path in self.paths]}

    def close(self):
        self.closed = True  # In-flight bounded reads are daemon threads; exit never waits on them.


def once(paths, *, timeout=5.0, collector=collect):
    refresh = Refresh(paths, collector=collector, timeout=timeout, interval=float("inf"))
    deadline = time.monotonic() + timeout
    try:
        refresh.poll()
        while refresh.pending and time.monotonic() < deadline:
            time.sleep(min(0.02, max(0, deadline - time.monotonic())))
            refresh.poll()
        refresh.poll()
        return refresh.snapshot()
    finally:
        refresh.close()
