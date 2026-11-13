"""Prepare an exact host run before pytest; never install or retry during a gate."""
import json
from pathlib import Path
import shlex
import shutil
import sys
import uuid

from verification_support.cpu_capacity import available_cpus
from verification_support.identity import source_identity
from verification_support.host_execution import validate_resources
from .config import load
from .environment import environment, digest
from .history import estimates
from .provision import check, python_path
from .snapshot import copy_snapshot, fingerprint, remote_verify, inventory
from .ssh import Transport
# Re-export the established helper imports; implementation lives in one contract.
from .contract import validate_profile, public_proof, verify_pool


def proxy_gateway(identifier, transport, executable, work):
    # The proxy serves concurrent forwarding channels, not pytest test bodies.
    # xdist keeps each separate worker on its main_thread_only execution model.
    return ('id=' + identifier + '//' + transport + '//python=' + executable
            + '//chdir=' + work + '//execmodel=thread')


def run_forecasts(selected, workers, measured, snapshot):
    """Project existing measurements onto this run; never alter history or selection."""
    identities = set(selected.values())
    hosts = {row['host'] for row in workers.values()}
    current = {key: value for key, value in measured.items()
               if key.rpartition('\n')[0] in identities
               and key.rpartition('\n')[2] in hosts}
    baseline = {row['test_id']: row['duration_ns'] / 1e9
                for row in (snapshot or {}).get('tests', [])
                if row['test_id'] in identities and row.get('duration_ns') is not None
                and row.get('valid', True)}
    return current, baseline


def prepare_pool(root, outdir, config, selected, snapshot, worker_limit):
    hosts = load(config)
    if any(h.ssh is not None for h in hosts) and not shutil.which('rsync'):
        raise ValueError('Coordinator needs rsync; run test-hosts prepare for the local host first')
    expected = environment()
    if expected['packages'].get('pytest-xdist') != '3.8.0' or expected['packages'].get('execnet') != '2.1.2':
        raise ValueError('Host runner requires the reviewed xdist 3.8.0 / execnet 2.1.2 protocol')
    source = source_identity(root)
    manifest = copy_snapshot(root, outdir / 'host-snapshot')
    key = uuid.uuid4().hex
    workers, proxies = {}, []
    endpoints = set()
    for host in hosts:
        transport = Transport(host)
        observed = check(host, expected, transport=transport)
        endpoint = observed['account']
        if endpoint in endpoints:
            raise ValueError('Two configured aliases resolve to the same execution account')
        endpoints.add(endpoint)
        if host.ssh is None:
            work = str(root)
            cpus = available_cpus()
            executable = sys.executable
            spec = 'popen'
        else:
            work = str(Path(host.directory) / 'runs' / key / 'source')
            transport.python('''import os,json
from pathlib import Path
base=Path(%r)
for path in (base,*base.parents):
    if path.is_symlink(): raise ValueError('linked host root')
if base.stat().st_uid!=os.getuid() or base.stat().st_mode & 0o077: raise ValueError('host root is not private')
runs=base/'runs'
if runs.is_symlink(): raise ValueError('linked runs directory')
runs.mkdir(mode=0o700,exist_ok=True)
run=runs/%r
run.mkdir(mode=0o700)
(run/'source').mkdir(mode=0o700)
print(json.dumps(True))
''' % (host.directory, key))
            transport.copy(str(outdir / 'host-snapshot') + '/', work + '/')
            transport.python(remote_verify(work, manifest))
            executable = python_path(host, expected)
            capacity_script = ("import sys,json; sys.path.insert(0," + repr(work + '/tools') + "); "
                               "from verification_support.cpu_capacity import available_cpus; print(json.dumps(available_cpus()))")
            cpus = transport.python(capacity_script, executable=executable)
            proxy = 'srproxy' + str(len(proxies))
            ssh = shlex.join([*transport.options(), host.ssh])
            proxies.append(proxy_gateway(proxy, 'ssh=' + ssh, executable, work))
            spec = 'popen//via=' + proxy + '//python=' + executable
        count = min(cpus, host.workers, worker_limit)
        resources = dict(format_version=1, available_cpus=cpus, workers=count,
                         worker_limit=min(host.workers, worker_limit), nested=False, nice_minimum=10)
        validate_resources(resources)
        for _ in range(count):
            worker = 'gw' + str(len(workers))
            workers[worker] = dict(host=host.name, hostname=observed['hostname'], account=observed['account'], root=work,
                environment_sha256=digest(expected), resources=resources, speed=host.speed,
                spec=spec, budget=min(cpus, host.workers), remote=host.ssh is not None)
    measured, baseline = run_forecasts(selected, workers, estimates(root, digest(expected)), snapshot)
    profile = dict(format_version=1, source_sha256=source, snapshot_sha256=fingerprint(manifest),
                   environment=expected, workers=workers, proxies=proxies, selected=selected,
                   estimates=measured, baseline=baseline)
    if source_identity(root) != source or inventory(root) != manifest:
        raise ValueError('Source changed during remote preparation')
    path = outdir / 'host-run.json'
    validate_profile(profile)
    path.write_text(json.dumps(profile, sort_keys=True))
    path.chmod(0o600)
    return profile, path
