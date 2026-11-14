"""Pure host-run and evidence contracts, independent of SSH or test execution."""
import math
from pathlib import Path
import re

from verification_support.host_execution import validate_resources, verify_resources
from .environment import digest


def validate_profile(profile):
    fields = {'format_version', 'source_sha256', 'snapshot_sha256', 'environment', 'workers', 'proxies', 'selected', 'estimates', 'baseline'}
    if isinstance(profile, dict) and profile.get('format_version') == 2:
        fields.add('live')
    if not isinstance(profile, dict) or set(profile) != fields or type(profile['format_version']) is not int or profile['format_version'] not in (1, 2):
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
    if profile['format_version'] == 2:
        from dev.test_control.store import counts
        live = profile['live']
        if type(live) is not dict or set(live) != {'repository', 'home', 'overrides'}:
            raise ValueError('Invalid live host control binding')
        for key in ('repository', 'home'):
            if type(live[key]) is not str or not Path(live[key]).is_absolute() or '..' in Path(live[key]).parts:
                raise ValueError('Invalid live control location')
        overrides = counts(live['overrides'])
        if set(overrides) - groups.keys() or any(v > groups[k][0]['resources']['workers'] for k, v in overrides.items()):
            raise ValueError('Live override exceeds checked host capacity')
    return profile

def public_proof(profile):
    validate_profile(profile)
    return {'format_version': profile['format_version'], 'source_sha256': profile['source_sha256'],
            'snapshot_sha256': profile['snapshot_sha256'],
            'environment_sha256': digest(profile['environment']),
            'workers': {key: {k: row[k] for k in ('host', 'hostname', 'account', 'environment_sha256', 'resources', 'speed', 'budget', 'remote')}
                        for key, row in profile['workers'].items()}}

def verify_pool(observation, proof):
    if isinstance(proof, dict) and proof.get('format_version') == 2:
        return verify_live_pool(observation, proof)
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


def verify_live_pool(observation, proof):
    """Each actual attempt has one permission and one nonoverlapping host lease."""
    actual = observation.get('host_pool')
    if type(actual) is not dict or actual.get('binding') != proof or actual.get('errors'):
        raise ValueError('Live pool differs from the bound run')
    launched, workers = actual.get('launched'), actual.get('workers')
    if (type(launched) is not dict or type(workers) is not dict or not launched
            or not set(proof['workers']) <= set(launched) or set(launched) != set(workers)
            or set(workers) != set(observation.get('workers', []))):
        raise ValueError('Incomplete live worker evidence')
    selected = actual.get('selected')
    if type(selected) is not list or not selected or any(type(n) is not str for n in selected) or selected != observation.get('nodeids') or len(set(selected)) != len(selected):
        raise ValueError('Live selection differs from collected tests')
    grants = actual.get('grants')
    if type(grants) is not dict or set(grants) - workers.keys():
        raise ValueError('Unbound live permissions')
    leases, covered = {}, set()
    for name, template in launched.items():
        if not re.fullmatch(r'gw[0-9]+', name) or template not in proof['workers']:
            raise ValueError('Worker was not launched on a checked host')
        expected, row = proof['workers'][template], workers[name]
        if type(row) is not dict or (name in proof['workers'] and proof['workers'][name] != expected):
            raise ValueError('Live worker identity changed hosts')
        if (any(row.get(k) != expected[k] for k in ('host', 'hostname', 'account', 'environment_sha256'))
                or any(row.get(k) != proof[k] for k in ('source_sha256', 'snapshot_sha256'))
                or row.get('io_priority') != {'class': 2, 'priority': 7}):
            raise ValueError('Unbound live worker environment or priority')
        verify_resources({'host_resources': row.get('resources'),
                          'workers': list(range(expected['resources']['workers']))}, expected['resources'])
        attempts = row.get('leases')
        if (type(attempts) is not list or len(attempts) != observation['worker_test_counts'].get(name)
                or len(attempts) != len(grants.get(name, []))):
            raise ValueError('Missing per-attempt live leases')
        for attempt, permit in zip(attempts, grants.get(name, [])):
            if (type(attempt) is not dict or set(attempt) != {'nodeid', 'slot', 'start', 'end'}
                    or any(type(attempt[k]) is not int for k in ('slot', 'start', 'end'))
                    or not 0 <= attempt['slot'] < expected['budget'] or not 0 <= attempt['start'] <= attempt['end']
                    or type(permit) is not dict or set(permit) != {'index', 'slot'}
                    or type(permit['index']) is not int or type(permit['slot']) is not int or not 0 <= permit['index'] < len(selected)
                    or permit['slot'] != attempt['slot'] or selected[permit['index']] != attempt['nodeid']
                    or attempt['nodeid'] in covered):
                raise ValueError('Invalid, duplicate or unpermitted live test attempt')
            covered.add(attempt['nodeid'])
            leases.setdefault((row['account'], attempt['slot']), []).append((attempt['start'], attempt['end']))
    if covered != set(selected):
        raise ValueError('Live attempts do not cover the fixed selection')
    for intervals in leases.values():
        ordered = sorted(intervals)
        if any(a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
            raise ValueError('Live workers overlap on an atomic host slot')
