"""Independent source scheduling; reusable without importing curses or the CLI."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time

from .monitor_data import collect_history, collect_status, observed

COLLECTORS = {'status': collect_status, 'history': collect_history}


class Refresh:
    """One in-flight read per target/source; immutable snapshots for the UI.

    Status and history have independent schedules, including within one target.
    A database query has a deadline, and never runs in the terminal thread.
    """
    def __init__(self, paths, *, database=None, interval=5, history_interval=60, timeout=5):
        self.paths = paths
        self.database = database
        self.timeout = timeout
        self.intervals = {'status': interval, 'history': history_interval}
        self.pool = ThreadPoolExecutor(max_workers=min(32, max(1, len(paths) * 2)), thread_name_prefix='test-monitor')
        self.entries = {(str(p), source): {'value': None, 'future': None, 'next': 0,
                        'stale': False, 'error': None} for p in paths for source in COLLECTORS}

    def request(self, force=False):
        now = time.monotonic()
        for (path, source), state in self.entries.items():
            if state['future'] is None and (force or now >= state['next']):
                state['future'] = self.pool.submit(COLLECTORS[source], Path(path), self.database, self.timeout)
                state['next'] = now + self.intervals[source]

    def harvest(self):
        changed = False
        for (_, source), state in self.entries.items():
            future = state['future']
            if future is None or not future.done():
                continue
            try:
                value = future.result()
                report = value.get('report', value)
                error = report.get('error') if report.get('status') == 'unavailable' else None
                if error and state['value'] is not None:
                    state.update(stale=True, error=error)
                else:
                    state.update(value=value, stale=bool(error), error=error)
            except Exception as error:
                state.update(stale=True, error=str(error))
            state['future'] = None
            state['next'] = time.monotonic() + self.intervals[source]
            changed = True
        return changed

    def snapshot(self):
        result = []
        for path in self.paths:
            sources = {}
            for name in COLLECTORS:
                state = self.entries[(str(path), name)]
                sources[name] = {'data': state['value'], 'stale': state['stale'],
                                 'refreshing': state['future'] is not None, 'error': state['error']}
            result.append({'repository': str(path), **sources})
        return result

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)


def snapshot_once(paths, *, database=None, timeout=5):
    refresh = Refresh(paths, database=database, timeout=timeout)
    try:
        refresh.request()
        # Once deliberately reads every selected target exactly once; no polling,
        # service action, test execution or subsequent refresh is scheduled.
        for state in refresh.entries.values():
            try:
                state['future'].result()
            except Exception:
                pass  # harvest records the individual error without losing peers
        refresh.harvest()
        return {'format_version': 1, 'kind': 'specroad-test-monitor',
                'observed_at': observed(), 'repositories': refresh.snapshot()}
    finally:
        refresh.close()
