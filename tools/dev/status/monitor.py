"""CLI and independent refresh scheduling for the read-only test monitor."""
import argparse
import json
import math
from pathlib import Path
import sys

from .cli import HelperParser, Terminal
from .monitor_data import filtered, targets

from .monitor_refresh import COLLECTORS, Refresh, snapshot_once


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


def query_timeout(value):
    result = seconds(value)
    if not 0.1 <= result <= 30:
        raise argparse.ArgumentTypeError('Abfragebudget zwischen 0.1 und 30 Sekunden angeben.')
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
    mode.add_argument('--query-timeout', type=query_timeout, default=5, help='SQLite-Abfragebudget 0.1–30 Sekunden (Standard: 5)')
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
        paths = targets(repository or Path(__file__).resolve().parents[3], args.apply_dir,
                        all_targets=args.all, database=args.database)
        if args.once:
            report = snapshot_once(paths, database=args.database, timeout=args.query_timeout)
            if args.json:
                report = filtered_snapshot(report, args)
                print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
            else:
                from .monitor_view import render_once
                print(render_once(report, args))
            return 2 if any(t[s]['stale'] for t in report['repositories'] for s in COLLECTORS) else 0
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise ValueError('Die TUI braucht ein Terminal; für Skripte --once --json verwenden.')
        from .monitor_view import run_tui
        return run_tui(paths, args)
    except (ValueError, OSError, ImportError, RuntimeError, OverflowError) as error:
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
