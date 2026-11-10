"""An explicit diagnostic run; xdist schedules, native observations prove outcomes."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import uuid

from dev.test_hosts.snapshot import copy_snapshot
from verification_support.cpu_capacity import available_cpus
from verification_support.common import read_object
from verification_support.host_execution import lower_priority, select_workers, verify_resources
from verification_support.identity import source_identity, platform_identity
from verification_support.process_environment import test_environment
from verification_support.runtime_paths import database_path, policy

from .artifacts import capture
from .collect import pytest_arguments
from .common import digest, output_path, test_key, write_json
from .process import execute, interrupt_on_term
from .resources import cpu_slots
from .selection import history_path, slowest
from .store import Store


def execution_command(snapshot, directory, request, workers, limit, trace):
    files = sorted({node.split('::', 1)[0] for node in request['pairs']})
    # Avoid ARG_MAX for a very broad selection. The plugin applies the exact
    # saved IDs in either case, before native collection accounting runs.
    scopes = files if len(files) <= 100 else ['tests']
    return [trace, '-ff', '-ttt', '-T', '-yy', '-s', '64', '-o', str(directory / 'raw' / 'strace'),
            sys.executable, '-I', '-B', str(snapshot / 'tools/pytest_entry.py'),
            *pytest_arguments(snapshot), '-p', 'xdist.plugin', '-p', 'dev.profiling.pytest_plugin',
            '-n', str(workers), '--dist', 'worksteal', '--max-worker-restart=0',
            '--worker-limit', str(limit), '--sr-expected-tests', str(len(request['pairs'])),
            '--sr-observations', str(directory / 'observations.json'),
            '--sr-profile-request', str(directory / 'execution.json'),
            *[str(snapshot / name) for name in scopes]]


def check_observation(observation, pairs, code, resources):
    if (not pairs or not isinstance(observation, dict) or code != 0 or observation.get('pytest_exit_code') != 0 or
            observation.get('suite_passed') is not True or observation.get('errors') != [] or
            observation.get('nodeid_to_test_id') != pairs or observation.get('tests_run') != len(pairs) or
            observation.get('test_outcomes') != dict.fromkeys(pairs.values(), 'passed')):
        raise ValueError('Native observations do not prove this complete selected run passed')
    verify_resources(observation, resources)


def archive(store, run, directory, pairs):
    nodes = {test_key(node): node for node in pairs}
    files = sorted(p for p in directory.iterdir() if p.is_file())
    files.extend(sorted(p for p in (directory / 'raw').rglob('*') if p.is_file()))
    for path in files:
        node, pid = None, None
        if path.parent.name in nodes:
            node = nodes[path.parent.name]
        if path.name.startswith('strace.') and path.suffix[1:].isdigit():
            kind, pid = 'strace', int(path.suffix[1:])
        else:
            kind = 'cprofile' if path.suffix == '.pstats' else 'resources' if path.name == 'resources.jsonl' else 'metadata'
        capture(store, run, directory, path, kind=kind, nodeid=node, pid=pid)


def freeze(root, snapshot):
    before = source_identity(root)
    manifest = copy_snapshot(root, snapshot)
    if source_identity(root) != before or source_identity(snapshot) != before:
        raise ValueError('The source changed while preparing the profiling snapshot')
    # Historical fixed Exchange policies must not cause instrumented writes to
    # escape this private snapshot. Current unregistered copies resolve locally.
    history = database_path(snapshot, policy(snapshot))
    if not history.is_relative_to(snapshot / 'build'):
        raise ValueError('Snapshot runtime policy must resolve to its own build directory')
    for name in manifest:
        path = snapshot / name
        path.chmod(path.stat().st_mode & ~0o222)
    for path in sorted((p for p in snapshot.rglob('*') if p.is_dir()), reverse=True):
        path.chmod(path.stat().st_mode & ~0o222)
    # Snapshot root stays writable for its private build/runtime history.
    return before, manifest


def run(root, args, selectors):
    if sys.platform != 'linux' or not hasattr(os, 'sched_setaffinity'):
        raise ValueError('strace profiling and CPU pinning require Linux')
    trace = shutil.which('strace')
    if trace is None or any(importlib.util.find_spec(name) is None for name in ('pytest', 'xdist')):
        raise ValueError('Use the development interpreter with pytest, xdist and strace installed')
    database = output_path(root, args.database)
    history = history_path(root, args.history) if args.slowest else None
    if database == history:
        raise ValueError('Profiling must use its own database')
    lower_priority()
    environment = test_environment(os.environ)
    directory = database.parent / 'runs' / str(uuid.uuid4())
    output_path(root, directory / 'execution.json')
    directory.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.mkdir(mode=0o700)
    (directory / 'raw').mkdir(mode=0o700)
    identifier = directory.name
    settings = dict(mode='slowest' if args.slowest else 'all' if args.all else 'selection',
                    selectors=selectors, keyword=args.keyword, marker=args.marker,
                    count=args.slowest, history=str(history) if history else None,
                    worker_limit=args.worker_limit, platform=platform_identity(),
                    python=sys.executable, traced=True,
                    profiler='cProfile per setup/call/teardown in the test worker thread',
                    line_events='sys.monitoring for the test function on Python 3.12+')
    pairs, observation, code, error, status = {}, {}, None, None, 'failed'
    with Store(database, root, create=True) as store, interrupt_on_term():
        store.create_run(identifier, root, directory, settings)
        print(json.dumps(dict(run=identifier, database=str(database), directory=str(directory)), sort_keys=True), flush=True)
        try:
            snapshot = directory / 'snapshot'
            source, manifest = freeze(root, snapshot)
            write_json(directory / 'source-manifest.json', manifest)
            collection_request = dict(selectors=selectors, keyword=args.keyword,
                                      marker=args.marker, source_sha256=source)
            write_json(directory / 'collection-request.json', collection_request)
            collect_command = [sys.executable, '-I', '-B', str(snapshot / 'tools/profile_tests.py'),
                               '_collect', '--request', str(directory / 'collection-request.json'),
                               '--output', str(directory / 'collection.json')]
            collect_code = execute(collect_command, snapshot, environment, directory / 'collection.log')
            collected, _ = read_object(directory / 'collection.json')
            if (collect_code != 0 or collected.get('valid') is not True or
                    collected.get('source_sha256') != source or source_identity(snapshot) != source):
                raise ValueError('Fresh isolated collection was not completed')
            pairs = collected['pairs']
            historical = {}
            if args.slowest:
                pairs, historical = slowest(pairs, history, args.slowest)
            limit = min(args.worker_limit, len(pairs), available_cpus())
            workers, resources = select_workers(snapshot, limit, worker_limit=limit, environment=environment)
            cpus = cpu_slots()[:workers]
            if len(cpus) != workers:
                raise ValueError('Insufficient allowed CPU slots')
            request = dict(run=identifier, repository=str(root), snapshot=str(snapshot),
                           directory=str(directory), database=str(database), pairs=pairs,
                           selection_sha256=digest(pairs), source_sha256=source, cpus=cpus,
                           host_resources=resources)
            write_json(directory / 'selection.json', dict(**collection_request, pairs=pairs,
                       selection_sha256=digest(pairs), historical=historical))
            write_json(directory / 'execution.json', request)
            store.select(identifier, pairs, historical, source, digest(pairs), workers)
            command = execution_command(snapshot, directory, request, workers, limit, trace)
            store.running(identifier, command)
            code = execute(command, snapshot, environment, directory / 'pytest.log',
                           samples=directory / 'raw' / 'resources.jsonl')
            observation, _ = read_object(directory / 'observations.json')
            check_observation(observation, pairs, code, resources)
            if source_identity(snapshot) != source:
                raise ValueError('Profiled source changed during execution')
            pids = [row[0] for row in store.db.execute('SELECT DISTINCT pid FROM tests WHERE run_id=?', (identifier,))]
            if not pids or any(pid is None or not (directory / 'raw' / f'strace.{pid}').is_file()
                               or (directory / 'raw' / f'strace.{pid}').stat().st_size == 0 for pid in pids):
                raise ValueError('A selected test worker has no syscall trace')
            status = 'passed'
        except KeyboardInterrupt:
            status, error = 'interrupted', 'Interrupted; existing measurements and raw files are preserved'
        except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as exc:
            error = f'{type(exc).__name__}: {exc}'
        if not observation and (directory / 'observations.json').is_file():
            try:
                observation, _ = read_object(directory / 'observations.json')
            except (OSError, ValueError):
                pass
        try:
            # The subprocess has exited before any raw artifact is indexed.
            with store.db:
                store.db.execute('UPDATE runs SET status=? WHERE id=?', ('indexing', identifier))
            archive(store, identifier, directory, pairs)
        except (OSError, ValueError, sqlite3.Error, KeyboardInterrupt) as exc:
            status, error = 'incomplete', f'{error or ""}; artifact import: {type(exc).__name__}: {exc}'
        status = store.finish(identifier, status, code,
                              outcomes=observation.get('test_outcomes'), error=error)
        error = store.db.execute('SELECT error FROM runs WHERE id=?', (identifier,)).fetchone()[0]
        print(json.dumps(dict(run=identifier, status=status, error=error,
                              tests=len(pairs), directory=str(directory)), sort_keys=True), flush=True)
    return 0 if status == 'passed' else 130 if status == 'interrupted' else 1
