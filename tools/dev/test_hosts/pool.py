"""Prepare an exact host run before pytest; never install or retry during a gate."""
import json
import os
import math
from pathlib import Path
import re
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


def validate_profile(profile):
    fields = {'format_version', 'source_sha256', 'snapshot_sha256', 'environment', 'workers', 'proxies', 'selected', 'estimates', 'baseline'}
    if not isinstance(profile, dict) or set(profile) != fields or type(profile['format_version']) is not int or profile['format_version'] != 1:
        raise ValueError('Invalid host run format')
    for key in ('source_sha256', 'snapshot_sha256'):
        if not isinstance(profile[key], str) or not re.fullmatch('[0-9a-f]{64}', profile[key]):
            raise ValueError('Invalid host run hash')
    workers = profile['workers']
    if not isinstance(workers, dict) or not 1 <= len(workers) <= 4096 or set(workers) != {'gw' + str(i) for i in range(len(workers))}:
        raise ValueError('Invalid host worker identities')
    selected = profile['selected']
    if (not isinstance(selected, dict) or not selected or len(set(selected.values())) != len(selected)
            or any(not isinstance(n, str) or not n.startswith('tests/') or '::' not in n
                   or any(c in n for c in ('\n', '\r', '\0')) or '..' in Path(n.split('::')[0]).parts
                   or not isinstance(v, str) or not v for n, v in selected.items())):
        raise ValueError('Invalid host test selection')
    if not isinstance(profile['proxies'], list) or any(not isinstance(s, str) or not s.startswith('id=srproxy') or '\n' in s for s in profile['proxies']):
        raise ValueError('Invalid host proxies')
    groups = {}
    for name, row in workers.items():
        expected = {'host', 'hostname', 'account', 'root', 'environment_sha256', 'resources', 'speed', 'spec', 'budget', 'remote'}
        if not isinstance(row, dict) or set(row) != expected:
            raise ValueError('Invalid host worker profile')
        if (not isinstance(row['host'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', row['host'])
                or not isinstance(row['hostname'], str) or not row['hostname']
                or not isinstance(row['account'], str) or not re.fullmatch('[0-9a-f]{64}', row['account'])
                or not Path(row['root']).is_absolute() or '..' in Path(row['root']).parts
                or row['environment_sha256'] != digest(profile['environment'])
                or type(row['speed']) not in (int, float) or not math.isfinite(row['speed']) or not 0.01 <= row['speed'] <= 100
                or type(row['remote']) is not bool or type(row['budget']) is not int
                or not isinstance(row['spec'], str) or not row['spec'].startswith('popen')):
            raise ValueError('Invalid worker environment, identity or forecast')
        resources = validate_resources(row['resources'])
        if resources['nested'] or not resources['workers'] <= row['budget'] <= resources['available_cpus']:
            raise ValueError('Invalid host pool resource budget')
        groups.setdefault(row['host'], []).append(row)
    for rows in groups.values():
        if len(rows) != rows[0]['resources']['workers'] or any(r != rows[0] for r in rows):
            raise ValueError('Host workers disagree about their shared resource contract')
    for key in ('estimates', 'baseline'):
        values = profile[key]
        if not isinstance(values, dict) or any(not isinstance(k, str) or type(v) not in (int, float)
                or not math.isfinite(v) or not 0 <= v <= 259200 for k, v in values.items()):
            raise ValueError('Invalid scheduling estimate')
    return profile


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
            proxies.append('id=' + proxy + '//ssh=' + ssh + '//python=' + executable + '//chdir=' + work)
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
    profile = dict(format_version=1, source_sha256=source, snapshot_sha256=fingerprint(manifest),
                   environment=expected, workers=workers, proxies=proxies, selected=selected,
                   estimates=estimates(root, digest(expected)),
                   baseline={r['test_id']: r['duration_ns'] / 1e9 for r in (snapshot or {}).get('tests', [])
                             if r.get('duration_ns') is not None and r.get('valid', True)})
    if source_identity(root) != source or inventory(root) != manifest:
        raise ValueError('Source changed during remote preparation')
    path = outdir / 'host-run.json'
    validate_profile(profile)
    path.write_text(json.dumps(profile, sort_keys=True))
    path.chmod(0o600)
    return profile, path


def public_proof(profile):
    validate_profile(profile)
    return {'format_version': 1, 'source_sha256': profile['source_sha256'],
            'snapshot_sha256': profile['snapshot_sha256'],
            'environment_sha256': digest(profile['environment']),
            'workers': {key: {k: row[k] for k in ('host', 'hostname', 'account', 'environment_sha256', 'resources', 'speed', 'budget', 'remote')}
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
        if type(row) is not dict or type(expected) is not dict:
            raise ValueError('Invalid worker proof')
        if (row.get('host') != expected['host'] or row.get('hostname') != expected['hostname'] or row.get('account') != expected['account'] or row.get('environment_sha256') != expected['environment_sha256']
                or row.get('source_sha256') != proof['source_sha256'] or row.get('snapshot_sha256') != proof['snapshot_sha256']
                or row.get('io_priority') != {'class': 2, 'priority': 7}
                or type(row.get('slot')) is not int or not 0 <= row['slot'] < expected['budget']):
            raise ValueError('Unbound worker environment/source/priority/lease')
        verify_resources({'host_resources': row.get('resources'),
                          'workers': list(range(expected['resources']['workers']))}, expected['resources'])
    slots = [(row['account'], row['slot']) for row in actual['workers'].values()]
    if len(slots) != len(set(slots)):
        raise ValueError('Workers claim the same host slot')
