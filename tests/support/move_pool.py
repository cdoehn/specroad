"""Two checked execution roles, native local/proxy gateways, deterministic body."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys

from support.catalog_project import make_catalog_project
from dev.test_hosts.environment import environment, digest, account
from dev.test_hosts.pool import proxy_gateway
from dev.test_hosts.snapshot import copy_snapshot, fingerprint
from verification_support.cpu_capacity import available_cpus
from verification_support.host_execution import POLICY, POLICY_VALUE
from verification_support.identity import source_identity
from verification_support.process_environment import test_environment as isolated_environment


SUBJECT = '''from pathlib import Path
import os, subprocess, sys, tempfile, time, uuid
import pytest
folder = Path('build')
@pytest.fixture(autouse=True)
def fresh():
    folder.mkdir(exist_ok=True)
    # The real local/proxy worker must keep its inherited long TMPDIR while
    # the supervisor still offers a private, usable control endpoint.
    temporary = Path(os.environ['TMPDIR'])
    assert tempfile.gettempdir() == str(temporary)
    assert len(os.fsencode(temporary)) > 108
    endpoint = Path(os.environ['SPECROAD_ATTEMPT_SOCKET'])
    assert not endpoint.is_relative_to(temporary)
    assert endpoint.parent.stat().st_mode & 0o077 == 0
    (folder / ('fixture-' + os.environ['PYTEST_XDIST_WORKER'])).write_text(str(os.getpid()) + ':' + uuid.uuid4().hex)

def exercise(index):
    worker = os.environ['PYTEST_XDIST_WORKER']
    if index == 0 and worker == 'gw0':
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        (folder/'original-child').write_text(str(child.pid))
        (folder/'original').write_text(worker)
        deadline = time.monotonic()+50
        while not (folder/'release').exists() and time.monotonic()<deadline:
            time.sleep(.01)
        assert (folder/'release').exists()
    elif index == 0:
        (folder/'replacement').write_text(worker)
'''


@contextmanager
def pool(tmp_path, *, proxy=False, source=SUBJECT, transform=None):
    ids = [f'tests/test_subject.py::test_{i}' for i in range(6)]
    source += '\n'.join(f'def test_{i}():\n    exercise({i})\n' for i in range(6))
    root = make_catalog_project(tmp_path / 'source', ids=ids, source=source)
    (root / POLICY).write_text(json.dumps(POLICY_VALUE))
    remote = tmp_path / 'remote'
    manifest = copy_snapshot(root, remote)
    target = remote if proxy else root
    home = tmp_path / 'state/test-control'
    observed = environment()
    cpus = available_cpus()
    resources = dict(format_version=1, available_cpus=cpus, workers=1, worker_limit=1, nested=False, nice_minimum=10)
    workers = {}
    for index, (host, work, transport) in enumerate((('source', root, 'popen'), ('target', target, 'popen//via=srproxy0' if proxy else 'popen'))):
        executable = shlex.join([sys.executable, str(work/'tools/dev/test_hosts/attempt_supervisor.py')])
        workers['gw'+str(index)] = dict(host=host, hostname=platform.node(), account=account(), root=str(work),
            environment_sha256=digest(observed), resources=resources.copy(), speed=1.0,
            spec=transport+'//python='+executable, budget=min(2, cpus), remote=bool(proxy and index))
    profile = dict(format_version=3, source_sha256=source_identity(root), snapshot_sha256=fingerprint(manifest),
        environment=observed, workers=workers, proxies=[proxy_gateway('srproxy0', 'popen', sys.executable, str(target))] if proxy else [],
        selected={n:n for n in ids}, estimates={}, baseline={n: 100.0 if i == 0 else .01 for i,n in enumerate(ids)},
        live=dict(repository=str(root), home=str(home), overrides={}))
    if transform is not None:
        transform(profile)
    config = root/'build/host-run.json'; config.write_text(json.dumps(profile))
    log = tmp_path/'pool.log'
    temporary = tmp_path / ('long-worker-temp-' + 'x' * 120)
    temporary.mkdir(mode=0o700)
    env = isolated_environment(os.environ)
    env['TMPDIR'] = str(temporary)
    env.update(SPECROAD_NESTED_TEST_RUN='0', XDG_STATE_HOME=str(tmp_path/'state'), SPECROAD_TEST_CONTROL_HOME=str(home))
    args = ['-o', 'addopts=', '--disable-plugin-autoload', '-p', 'xdist.plugin', '-p', 'no:cacheprovider', '-p', 'no:doctest',
        '-n', '2', '--dist', 'worksteal', '--max-worker-restart=0', '--worker-limit', '2', '--sr-host-run', str(config),
        '--sr-expected-tests', '6', '--sr-observations', str(root/'build/observations.json'), *ids]
    with log.open('w') as stream:
        process = subprocess.Popen([sys.executable, '-I', '-B', str(root/'tools/pytest_entry.py'), *args],
            cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
        try:
            yield dict(root=root, target=target, home=home, process=process, log=log, profile=profile, cpus=cpus)
        finally:
            for path in (root, target):
                (path/'build').mkdir(exist_ok=True)
                (path/'build/release').touch()
            try:
                process.wait(timeout=40)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=5)
