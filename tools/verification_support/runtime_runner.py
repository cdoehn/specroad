"""Explicit complete or freely selected timing runs using pytest's own scheduler."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from .catalog_check import run_catalog_preflight
from .ci_reference import _load_report
from .common import json_bytes
from .identity import source_identity
from .process_environment import test_environment
from .publication import publish_report
from .runtime_store import TimingStore, binding, journal_path, read_store


def choose(pairs, *, files=(), identities=(), selections=()):
    files = list(files)
    identities = list(identities)
    for path in selections:
        value = _load_report(Path(path))
        if (type(value) is not dict or set(value) != {'test_files', 'test_ids'}
                or any(type(value[k]) is not list or any(type(v) is not str for v in value[k]) for k in value)):
            raise ValueError('Selection file requires test_files and test_ids lists')
        files.extend(value['test_files'])
        identities.extend(value['test_ids'])
    wanted = {}
    for name in files:
        found = {n: i for n, i in pairs.items() if n.split('::', 1)[0] == name}
        if not found:
            raise ValueError('Unknown test file: ' + name)
        wanted.update(found)
    for identity in identities:
        found = {n: i for n, i in pairs.items() if identity in (n, i)}
        if len(found) != 1:
            raise ValueError('Unknown or ambiguous test identity: ' + identity)
        wanted.update(found)
    return dict(sorted(wanted.items()))


def prepare_request(root, journal, workers, *, all_tests=False, remaining=False,
                    files=(), identities=(), selections=(), keep_complete=False):
    root = Path(root).resolve()
    if type(workers) is not int or workers < 2:
        raise ValueError('Timing measurements require at least two workers')
    journal = journal_path(journal, root)
    parent = root / 'build'
    parent.mkdir(exist_ok=True)
    journal_path(parent / 'timing-probe', root)
    work = Path(tempfile.mkdtemp(prefix='runtime-measurement-', dir=parent))
    catalog_path = work / 'catalog.json'
    if not run_catalog_preflight(root, catalog_path):
        raise ValueError('Complete collection/catalog preflight failed')
    catalog = _load_report(catalog_path)
    pairs = catalog['nodeid_to_test_id']
    expected = binding(catalog['source_sha256'], pairs, workers)
    complete = {}
    if journal.exists():
        # Explicit measurement may recover SQLite's interrupted transaction.
        # Status stays read-only. The writer lease excludes a concurrent run.
        store = TimingStore(journal, root, expected)
        try:
            _, complete, _ = read_store(journal, root)
        finally:
            store.close()
    selected = choose(pairs, files=files, identities=identities, selections=selections)
    explicit = bool(files or identities or selections)
    if all_tests:
        if explicit:
            raise ValueError('Use all tests or a free selection')
        selected = pairs
    elif remaining and not explicit:
        selected = pairs
    elif not explicit:
        raise ValueError('Choose all, remaining, or explicit tests/files')
    if not keep_complete:
        selected = {n: i for n, i in selected.items() if n not in complete}
    if source_identity(root) != expected['source_sha256']:
        raise ValueError('Source changed while preparing the measurement')
    request = {'format_version': 1, 'binding': expected, 'selected': dict(sorted(selected.items()))}
    path = work / 'request.json'
    publish_report(path, root, request)
    return path, request


def run_measurement(root, journal, workers, **selection):
    path, request = prepare_request(root, journal, workers, **selection)
    if not request['selected']:
        return 0
    nodes = path.parent / 'nodeids.txt'
    nodes.write_text('\n'.join(request['selected']) + '\n')
    command = [sys.executable, '-I', '-B', str(Path(root) / 'tools/pytest_entry.py'),
        '-o', 'addopts=', '--disable-plugin-autoload', '-p', 'no:cacheprovider', '-p', 'no:doctest',
        '-p', 'xdist.plugin', '-n', str(workers), '--dist', 'load', '--max-worker-restart=0',
        '--sr-expected-tests', str(len(request['selected'])),
        '--sr-runtime-journal', str(Path(journal).absolute()), '--sr-timing-request', str(path),
        '--sr-observations', str(path.parent / 'observations.json'), '@' + str(nodes)]
    return subprocess.run(command, cwd=root, env=test_environment(os.environ),
                          stdin=subprocess.DEVNULL, check=False).returncode
