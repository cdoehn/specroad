"""Pure host-run and evidence contracts, independent of SSH or test execution."""
import math
from pathlib import Path
import re

from verification_support.host_execution import validate_resources, verify_resources
from .environment import digest


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
