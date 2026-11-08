"""Prepare an exact host run before pytest; never install or retry during a gate."""
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import uuid

from verification_support.cpu_capacity import available_cpus
from verification_support.identity import source_identity
from verification_support.host_execution import validate_resources, verify_resources
from .config import load, read_json
from .environment import environment, digest
from .history import estimates
from .provision import check, python_path
from .snapshot import copy_snapshot, fingerprint, remote_verify, inventory
from .ssh import Transport


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
        endpoint = (observed['hostname'], observed['uid'])
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
            transport.run(['mkdir', '-p', work])
            transport.copy(str(outdir / 'host-snapshot') + '/', work + '/')
            transport.python(remote_verify(work, manifest))
            executable = python_path(host, expected)
            capacity_script = ("import sys,json; sys.path.insert(0," + repr(work + '/tools') + "); "
                               "from verification_support.cpu_capacity import available_cpus; print(json.dumps(available_cpus()))")
            cpus = transport.python(capacity_script, executable=executable)
            proxy = 'srproxy' + str(len(proxies))
            ssh = shlex.join([*transport.options(), host.ssh])
            proxies.append('id=' + proxy + '//ssh=' + ssh + '//python=' + executable + '//chdir=' + work)
            spec = 'popen//via=' + proxy + '//python=' + executable
        count = min(cpus, host.workers, worker_limit)
        resources = dict(format_version=1, available_cpus=cpus, workers=count,
                         worker_limit=min(host.workers, worker_limit), nested=False, nice_minimum=10)
        validate_resources(resources)
        for _ in range(count):
            worker = 'gw' + str(len(workers))
            workers[worker] = dict(host=host.name, hostname=observed['hostname'], root=work,
                environment_sha256=digest(expected), resources=resources, speed=host.speed,
                spec=spec, budget=min(cpus, host.workers), remote=host.ssh is not None)
    profile = dict(format_version=1, source_sha256=source, snapshot_sha256=fingerprint(manifest),
                   environment=expected, workers=workers, proxies=proxies, selected=selected,
                   estimates=estimates(root, digest(expected)),
                   baseline={r['test_id']: r['duration_ns'] / 1e9 for r in (snapshot or {}).get('tests', [])
                             if r.get('duration_ns') is not None and r.get('valid', True)})
    if source_identity(root) != source or inventory(root) != manifest:
        raise ValueError('Source changed during remote preparation')
    path = outdir / 'host-run.json'
    path.write_text(json.dumps(profile, sort_keys=True))
    path.chmod(0o600)
    return profile, path


def public_proof(profile):
    return {'format_version': 1, 'source_sha256': profile['source_sha256'],
            'snapshot_sha256': profile['snapshot_sha256'],
            'environment_sha256': digest(profile['environment']),
            'workers': {key: {k: row[k] for k in ('host', 'hostname', 'environment_sha256', 'resources', 'speed', 'budget', 'remote')}
                        for key, row in profile['workers'].items()}}


def verify_pool(observation, proof):
    if not isinstance(proof, dict) or proof.get('format_version') != 1 or not proof.get('workers'):
        raise ValueError('Missing host pool proof')
    actual = observation.get('host_pool')
    if not isinstance(actual, dict) or actual.get('binding') != proof or actual.get('errors'):
        raise ValueError('Host pool differs from bound run')
    if set(actual.get('workers', {})) != set(proof['workers']) or set(observation.get('workers', [])) != set(proof['workers']):
        raise ValueError('Host pool worker set mismatch')
    for name, expected in proof['workers'].items():
        row = actual['workers'][name]
        if (row.get('host') != expected['host'] or row.get('environment_sha256') != expected['environment_sha256']
                or row.get('source_sha256') != proof['source_sha256'] or row.get('snapshot_sha256') != proof['snapshot_sha256']
                or row.get('io_priority') != {'class': 2, 'priority': 7}
                or type(row.get('slot')) is not int or not 0 <= row['slot'] < expected['budget']):
            raise ValueError('Unbound worker environment/source/priority/lease')
        verify_resources({'host_resources': row.get('resources'),
                          'workers': list(range(expected['resources']['workers']))}, expected['resources'])
