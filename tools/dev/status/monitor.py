"""CLI and independent refresh scheduling for the read-only test monitor."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
import sys
import time

from .cli import HelperParser, Terminal
from .monitor_data import collect_history, collect_status, filtered, observed, targets

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


def filtered_snapshot(report, args):
    for target in report['repositories']:
        for name in COLLECTORS:
            data = target[name]['data']
            if data is None:
                continue
            rows, count = filtered(data['tests'], match=args.match, minimum=args.min_seconds,
                sort=args.sort, descending=not args.ascending, limit=args.limit)
            data['tests'] = rows
            data['matching_tests'] = count
            data['truncated'] = count > len(rows)
    report['filters'] = {'match': args.match, 'min_seconds': args.min_seconds,
                        'sort': args.sort, 'descending': not args.ascending, 'limit': args.limit}
    return report


def seconds(value):
    try:
        result = float(value)
        if not math.isfinite(result) or result < 0:
            raise ValueError
        return result
    except ValueError:
        raise argparse.ArgumentTypeError('Eine endliche Zahl ab 0 angeben.') from None


def interval(value):
    result = seconds(value)
    if not 1 <= result <= 3600:
        raise argparse.ArgumentTypeError('Intervall zwischen 1 und 3600 Sekunden angeben.')
    return result


def limit(value):
    result = int(value)
    if not 0 <= result <= 100000:
        raise argparse.ArgumentTypeError('0 (alle) oder höchstens 100000 Zeilen angeben.')
    return result


class Parser(HelperParser):
    def error(self, message):
        raise ValueError(message)


def parser(argv):
    result = Parser(prog='test-monitor', description='Mehrere Apply-Ziele und ihre Testphasen beobachten. Nur lesend.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Beispiele:\n  python3 tools/test-monitor --all\n'
               '  python3 tools/test-monitor --apply-dir ../specroad-apply --apply-dir ../specroad-apply2\n'
               '  python3 tools/test-monitor --all --once --json\n'
               '  python3 tools/test-monitor --once --match merge --sort call --min-seconds 600\n'
               '\nTUI: Tab Fokus, Pfeile Auswahl, 1–4 Ansicht, / Suche, t Zeiten, [ ] Sortierfeld,\n'
               'd Dauer/Richtung, n Name, r Aktualisieren, ? Hilfe, q Ende. Keine Dienststarts.')
    result.display_title = 'TEST MONITOR'
    result.display_args = argv
    sources = result.add_argument_group('Quellen')
    sources.add_argument('--apply-dir', type=Path, action='append', default=[], metavar='PFAD',
                         help='Apply-Ziel, wiederholbar; sonst Linie dieser Repository-Kopie')
    sources.add_argument('--all', action='store_true', help='Apply-Verzeichnisse neben dieser Repository-Kopie')
    sources.add_argument('--database', type=Path, help='explizite Datenbank für genau ein Ziel, nur lesend')
    mode = result.add_argument_group('Betrieb')
    mode.add_argument('--once', action='store_true', help='einmal lesen und beenden, ohne TUI')
    mode.add_argument('--json', action='store_true', help='maschinenlesbare Momentaufnahme; setzt --once voraus')
    mode.add_argument('--interval', type=interval, default=5, help='Statusabfrage in Sekunden (Standard: 5)')
    mode.add_argument('--history-interval', type=interval, default=60, help='Laufzeithistorie in Sekunden (Standard: 60)')
    mode.add_argument('--query-timeout', type=interval, default=5, help='SQLite-Abfragebudget in Sekunden (Standard: 5)')
    filters = result.add_argument_group('Testliste')
    filters.add_argument('--match', default='', metavar='TEXT', help='Teiltextsuche in Testname und Node-ID')
    filters.add_argument('--min-seconds', type=seconds, default=0, help='Mindestdauer im gewählten Sortierfeld')
    filters.add_argument('--sort', choices=('total', 'setup', 'call', 'teardown', 'elapsed', 'name'), default='total')
    filters.add_argument('--ascending', action='store_true', help='aufsteigend sortieren, fehlende Werte zuletzt')
    filters.add_argument('-n', '--limit', type=limit, default=200, help='Zeilen nach Suche/Sortierung (0: alle, Standard: 200)')
    display = result.add_argument_group('Darstellung')
    display.add_argument('--view', choices=('status', 'running', 'runtimes', 'failures'), default='status')
    display.add_argument('--time-view', choices=('total', 'phases', 'both'), default='both')
    display.add_argument('--color', choices=('auto', 'always', 'never'), default='auto')
    display.add_argument('--no-color', dest='color', action='store_const', const='never')
    display.add_argument('--plain', action='store_true', help='Einmalausgabe ohne Farben/grafische Zeichen')
    return result


def main(repository=None, argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        args = parser(argv).parse_args(argv)
        if args.json and not args.once:
            raise ValueError('--json benötigt --once.')
        if args.sort == 'name' and args.min_seconds:
            raise ValueError('--min-seconds benötigt ein Zeitfeld als --sort.')
        paths = targets(repository or Path(__file__).resolve().parents[3], args.apply_dir,
                        all_targets=args.all, database=args.database)
        if args.once:
            report = filtered_snapshot(snapshot_once(paths, database=args.database, timeout=args.query_timeout), args)
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
            else:
                from .monitor_view import render_once
                print(render_once(report, args))
            return 2 if any(t[s]['stale'] for t in report['repositories'] for s in COLLECTORS) else 0
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise ValueError('Die TUI braucht ein Terminal; für Skripte --once --json verwenden.')
        from .monitor_view import run_tui
        return run_tui(paths, args)
    except (ValueError, OSError, ImportError) as error:
        if '--json' in argv:
            print(json.dumps({'format_version': 1, 'kind': 'specroad-test-monitor',
                              'status': 'unavailable', 'error': str(error)}, ensure_ascii=False))
        else:
            ui = Terminal('never' if '--no-color' in argv else 'auto')
            ui.header('TEST MONITOR', 'Fehler')
            ui.line(str(error), 'red')
            print(str(ui), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
