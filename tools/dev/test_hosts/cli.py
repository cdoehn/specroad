"""Explicit host administration. A check never installs or starts a test."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from .config import config_path, load
from .provision import check, prepare
from .ssh import Transport


def main(argv=None):
    parser = argparse.ArgumentParser(description='SpecRoad Apply-Testhosts: SSH, Umgebung und Vorbereitung')
    parser.add_argument('--config', type=Path, help='Lokale Hostdatei; Standard ~/.config/specroad/test-hosts.json')
    parser.add_argument('--json', action='store_true', help='Einmalige maschinenlesbare Ausgabe')
    actions = parser.add_subparsers(dest='action', required=True)
    for name in ('list', 'check', 'prepare', 'connect', 'status', 'disconnect'):
        sub = actions.add_parser(name)
        sub.add_argument('hosts', nargs='*', help='Hostnamen; ohne Namen alle konfigurierten Hosts')
        if name == 'prepare':
            sub.add_argument('--uv', type=Path, help='Geprüfte lokale uv-Binärdatei für verwaltetes CPython')
            sub.add_argument('--non-interactive', action='store_true', help='Kein Passwortdialog; sudo -n')
    args = parser.parse_args(argv)
    rows, failed = [], False
    try:
        hosts = load(config_path(args.config))
        if set(args.hosts) - {h.name for h in hosts}:
            raise ValueError('Unbekannter Hostname')
        for host in hosts:
            if args.hosts and host.name not in args.hosts:
                continue
            try:
                if args.action == 'list':
                    row = host.value()
                elif args.action == 'check':
                    row = check(host)
                elif args.action == 'prepare':
                    if args.json and not args.non_interactive:
                        raise ValueError('JSON-Vorbereitung benötigt --non-interactive; Dialoge vorher mit connect öffnen')
                    row = prepare(host, uv=args.uv, non_interactive=args.non_interactive)
                else:
                    if args.json and args.action == 'connect':
                        raise ValueError('connect verwendet den nativen SSH-Dialog; ohne --json aufrufen')
                    row = Transport(host).control(args.action)
                rows.append({'host': host.name, 'ok': True, **row})
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                rows.append({'host': host.name, 'ok': False, 'error': str(error)})
                failed = True
    except (OSError, ValueError, TypeError) as error:
        rows.append({'ok': False, 'error': str(error)})
        failed = True
    if args.json:
        print(json.dumps({'format_version': 1, 'action': args.action, 'ok': not failed, 'hosts': rows}, sort_keys=True))
    else:
        color = sys.stdout.isatty()
        for row in rows:
            mark = 'OK' if row['ok'] else 'FEHLER'
            prefix = ('\033[32m' if row['ok'] else '\033[31m') if color else ''
            suffix = '\033[0m' if color else ''
            print(f'{prefix}{mark:<7}{suffix} {row.get("host", "Konfiguration")}: ' +
                  (row.get('error') or json.dumps({k: v for k, v in row.items() if k not in ('host', 'ok')}, ensure_ascii=False)))
    return 1 if failed else 0
