"""Independent bounded refresh and CLI for the read-only Control monitor."""
import argparse
import json
import math
import sys
from .errors import ControlError
from .monitor_data import discover
from .monitor_refresh import Refresh, once


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
