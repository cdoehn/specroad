"""Independent bounded refresh and CLI for the read-only Control monitor."""
import argparse
from copy import deepcopy
import json
import math
import queue
import sys
import threading
import time
from .errors import ControlError
from .monitor_data import collect, discover


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


def seconds(value):
    try:
        result = float(value)
        if not math.isfinite(result) or not 0.1 <= result <= 60:
            raise ValueError
        return result
    except ValueError:
        raise argparse.ArgumentTypeError('Eine endliche Zahl zwischen 0.1 und 60 angeben.') from None


def main(argv=None):
    parser = argparse.ArgumentParser(prog='control-monitor', description='Control-Instanzen beobachten. Nur lesend.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--instance', help='Eine benannte Instanz; sonst default bzw. die Umgebungsauswahl')
    group.add_argument('--all', action='store_true', help='Standardinstanz und benannte Instanzen anzeigen')
    parser.add_argument('--once', action='store_true', help='Einmal lesen und beenden')
    parser.add_argument('--json', action='store_true', help='JSON ausgeben; benötigt --once')
    parser.add_argument('--interval', type=seconds, default=5.0)
    parser.add_argument('--query-timeout', type=seconds, default=5.0)
    args = parser.parse_args(argv)
    if args.json and not args.once:
        parser.error('--json benötigt --once')
    try:
        paths, errors = discover(args.instance, all_instances=args.all)
        if args.once:
            report = once(paths, timeout=args.query_timeout)
            report['discovery_errors'] = errors
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
            else:
                from .monitor_view import render_once
                print(render_once(report))
            return 2 if errors or any(row['stale'] or row.get('errors') for row in report['instances']) else 0
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise ControlError('terminal_required', 'Die TUI braucht ein Terminal; --once --json funktioniert ohne TTY.')
        from .monitor_view import run_tui
        return run_tui(paths, args, errors)
    except (ControlError, OSError, ValueError, ImportError) as exc:
        error = {'kind': 'specroad-control-monitor', 'error': getattr(exc, 'code', type(exc).__name__), 'message': str(exc)}
        print(json.dumps(error, ensure_ascii=False) if args.json else str(exc), file=sys.stdout if args.json else sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
