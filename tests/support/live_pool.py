"""Small native xdist pool with isolated local/proxy transport and control home."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from support.catalog_project import make_catalog_project
from dev.test_hosts.environment import environment, digest, account
from dev.test_hosts.pool import proxy_gateway
from dev.test_hosts.snapshot import copy_snapshot, fingerprint
from verification_support.cpu_capacity import available_cpus
from verification_support.host_execution import POLICY, POLICY_VALUE
from verification_support.identity import source_identity
from verification_support.process_environment import test_environment as isolated_environment


def await_value(probe, process, log, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = probe()
        if value:
            return value
        if process.poll() is not None:
            raise AssertionError(log.read_text())
        time.sleep(0.02)
    raise AssertionError('Native live pool did not reach its bounded handshake\n' + log.read_text())


@contextmanager
def pool(tmp_path, *, proxy=True, initial=None, source=None, state=None, transform=None):
    ids = [f'tests/test_subject.py::test_{i}' for i in range(6)]
    body = source or '''from pathlib import Path
import os, threading, time
def exercise(index):
    assert threading.current_thread() is threading.main_thread()
    folder = Path('build')
    folder.mkdir(exist_ok=True)
    (folder / ('started-' + str(index))).write_text(os.environ['PYTEST_XDIST_WORKER'])
    end = time.monotonic() + 25
    while not (folder / 'release').exists() and time.monotonic() < end:
        time.sleep(0.01)
    assert (folder / 'release').exists()
'''
    body += '\n'.join(f'def test_{i}():\n    exercise({i})\n' for i in range(6))
    root = make_catalog_project(tmp_path / 'controller', ids=ids, source=body)
    (root / POLICY).write_text(json.dumps(POLICY_VALUE))
    target = tmp_path / 'remote-source' if proxy else root
    manifest = copy_snapshot(root, target) if proxy else copy_snapshot(root, tmp_path / 'snapshot')
    state = state or tmp_path / 'private-state'
    home = state / 'test-control'
    capacity = min(2, available_cpus())
    expected = environment()
    resources = dict(format_version=1, available_cpus=available_cpus(), workers=capacity,
                     worker_limit=capacity, nested=False, nice_minimum=10)
    row = dict(host='test-host', hostname=platform.node(), account=account(), root=str(target),
               environment_sha256=digest(expected), resources=resources, speed=1.0,
               spec=('popen//via=srproxy0//python=' + sys.executable) if proxy else 'popen',
               budget=capacity, remote=proxy)
    profile = dict(format_version=2, source_sha256=source_identity(root), snapshot_sha256=fingerprint(manifest),
        environment=expected, workers={f'gw{i}': row.copy() for i in range(capacity)},
        proxies=[proxy_gateway('srproxy0', 'popen', sys.executable, str(target))] if proxy else [],
        selected={n:n for n in ids}, estimates={}, baseline=dict.fromkeys(ids, 1.0),
        live=dict(repository=str(root), home=str(home), overrides={} if initial is None else {'test-host': initial}))
    if transform is not None:
        transform(profile)
    path = root / 'build/host-run.json'; path.write_text(json.dumps(profile))
    args = ['-o', 'addopts=', '--disable-plugin-autoload', '-p', 'xdist.plugin', '-p', 'no:cacheprovider',
        '-p', 'no:doctest', '-n', str(capacity), '--dist', 'worksteal', '--max-worker-restart=0',
        '--worker-limit', str(capacity), '--sr-host-run', str(path), '--sr-expected-tests', '6',
        '--sr-observations', str(root / 'build/observations.json'), *ids]
    env = isolated_environment(os.environ)
    env.update(SPECROAD_NESTED_TEST_RUN='0', XDG_STATE_HOME=str(state), SPECROAD_TEST_CONTROL_HOME=str(home))
    log = tmp_path / 'pool.log'
    with log.open('w') as output:
        process = subprocess.Popen([sys.executable, '-I', '-B', str(root / 'tools/pytest_entry.py'), *args],
            cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT)
        try:
            yield dict(root=root, target=target, profile=profile, process=process, log=log, home=home, capacity=capacity)
        finally:
            # Release deterministic body handshakes even after a failed assertion.
            (target / 'build').mkdir(exist_ok=True)
            (target / 'build/release').touch()
            try:
                process.wait(timeout=40)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=5)
