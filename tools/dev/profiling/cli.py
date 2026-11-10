"""Small explicit CLI: run, inspect, or export; no implicit test execution."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

from verification_support.host_execution import positive_limit
from .common import output_path, relative_selector


def parser(root):
    result = argparse.ArgumentParser(description='Profile selected SpecRoad tests with cProfile and strace')
    commands = result.add_subparsers(dest='command', required=True)
    launch = commands.add_parser('run', help='Explicitly collect and profile one selected run')
    launch.add_argument('--all', action='store_true', help='All currently collected tests')
    launch.add_argument('--slowest', type=positive_limit, metavar='N', help='N slowest valid latest measurements (e.g. 10)')
    launch.add_argument('--test', action='append', default=[], metavar='PATH_OR_NODEID', help='Repeat for a union of tests, files or directories')
    launch.add_argument('--selection', type=Path, help='JSON array of test paths / pytest node IDs; combines with --test')
    launch.add_argument('-k', dest='keyword', default='', help='pytest name expression')
    launch.add_argument('-m', dest='marker', default='', help='pytest marker expression')
    launch.add_argument('--history', type=Path, help='Read-only ranking history; default: this repository lane')
    launch.add_argument('--worker-limit', type=positive_limit, default=10)
    status = commands.add_parser('status', help='Read saved run states without collecting or executing tests')
    status.add_argument('--run', help='Show this run, including selected test states and artifact IDs')
    export = commands.add_parser('export', help='Export one lossless raw artifact from SQLite')
    export.add_argument('--artifact', type=positive_limit, required=True)
    export.add_argument('--output', type=Path, required=True)
    for command in (launch, status, export):
        command.add_argument('--database', type=Path, default=root / 'build/profiling/profiles.sqlite3')
    internal = commands.add_parser('_collect', help=argparse.SUPPRESS)
    internal.add_argument('--request', type=Path, required=True)
    internal.add_argument('--output', type=Path, required=True)
    return result


def selectors(root, args):
    explicit = bool(args.test or args.selection)
    if sum((args.all, bool(args.slowest), explicit)) > 1:
        raise ValueError('Choose --all, --slowest N, or a custom selection')
    if not (args.all or args.slowest or explicit or args.keyword or args.marker):
        raise ValueError('An explicit selection is required; use --all, --slowest 10, --test, --selection, -k or -m')
    if args.history is not None and not args.slowest:
        raise ValueError('--history is only used with --slowest')
    values = list(args.test)
    if args.selection is not None:
        extra = json.loads(args.selection.read_text())
        if not isinstance(extra, list) or not extra or any(not isinstance(v, str) for v in extra):
            raise ValueError('Selection files contain a nonempty JSON array of paths / node IDs')
        values.extend(extra)
    return list(dict.fromkeys(relative_selector(root, value) for value in values or ['tests']))


def show_status(database, identifier):
    from .store import reader
    with reader(database) as db:
        if identifier is None:
            rows = db.execute('SELECT id,created,finished,status,workers,error FROM runs ORDER BY created DESC LIMIT 50')
            return dict(runs=[dict(row) for row in rows])
        run = db.execute('SELECT * FROM runs WHERE id=?', (identifier,)).fetchone()
        if run is None:
            raise ValueError('Unknown profiling run')
        return dict(run=dict(run), tests=[dict(row) for row in db.execute(
            'SELECT nodeid,test_id,status,outcome,worker,cpu,started_ns,finished_ns FROM tests WHERE run_id=? ORDER BY ordinal', (identifier,))],
            artifacts=[dict(row) for row in db.execute(
            'SELECT id,path,kind,nodeid,pid,state,byte_count,sha256 FROM artifacts WHERE run_id=? ORDER BY id', (identifier,))])


def main(root, argv=None):
    root = Path(root).resolve()
    args = parser(root).parse_args(argv)
    try:
        if args.command == '_collect':
            from .collect import collect
            return collect(root, args.request, args.output)
        if args.command == 'run':
            selected = selectors(root, args)
            from .runner import run
            return run(root, args, selected)
        if args.command == 'status':
            print(json.dumps(show_status(args.database, args.run), sort_keys=True))
            return 0
        from .artifacts import export
        from .store import reader
        output = output_path(root, args.output)
        with reader(args.database) as db:
            export(db, args.artifact, output)
        print(json.dumps(dict(artifact=args.artifact, output=str(output)), sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        return 2
