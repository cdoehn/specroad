"""Operator CLI: persistent defaults, exact-run worker changes and JSON status."""
import argparse
import json
from pathlib import Path
import sys

from dev.status.cli import Target
from .store import change, configure, read_status


def main(argv=None):
    parser = argparse.ArgumentParser(description='Worker eines laufenden Apply-Testpools steuern')
    parser.add_argument('--apply-dir', type=Path)
    parser.add_argument('--json', action='store_true')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('status')
    config = commands.add_parser('config', help='Vorgaben für den nächsten Testlauf lesen/setzen')
    config.add_argument('--host')
    config.add_argument('--workers', type=int)
    workers = commands.add_parser('workers', help='Sollzahl im genau bezeichneten laufenden Gate ändern')
    workers.add_argument('--run', required=True)
    workers.add_argument('--host', required=True)
    workers.add_argument('--workers', required=True, type=int)
    relocation = commands.add_parser('move', help='Genau einen Versuch beenden und mit frischen Fixtures verlagern')
    relocation.add_argument('--run', required=True)
    relocation.add_argument('--attempt', required=True)
    relocation.add_argument('--target-host', required=True)
    args = parser.parse_args(argv)
    repository = args.apply_dir or Target.from_repository(Path(__file__).resolve().parents[3]).repository
    try:
        if args.command == 'status':
            value = read_status(repository)
        elif args.command == 'config':
            if (args.host is None) != (args.workers is None):
                parser.error('--host und --workers gemeinsam angeben')
            value = configure(repository, None if args.host is None else {args.host: args.workers})
        elif args.command == 'move':
            from .moves import move
            value = move(repository, args.run, args.attempt, args.target_host)
        else:
            value = change(repository, args.run, {args.host: args.workers})
        if args.json:
            print(json.dumps(value, sort_keys=True))
        elif args.command == 'status':
            if not value:
                print('Kein steuerbarer Testlauf registriert.')
            else:
                print(('AKTIV' if value['active'] else 'BEENDET') + ' · ' + value['run'])
                for host, desired in value['desired'].items():
                    actual = value['hosts'].get(host, {})
                    print(f'{host}: Soll {desired}, laufend {actual.get("running", 0)}, Prozesse {actual.get("processes", 0)}')
                for token, attempt in value.get('attempts', {}).items():
                    print(f"{token} · {attempt['host']} · {attempt['state']} · {attempt['nodeid']}")
                for receipt in value.get('moves', {}).values():
                    print(f"MOVE {receipt['id']}: {receipt['state']} · {receipt.get('reason', '')}")
        else:
            print(json.dumps(value, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'error': str(error)}) if args.json else str(error), file=sys.stderr)
        return 2
