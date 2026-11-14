"""One explicit attempt/target request, bound to the live controller generation."""
import re
import uuid

from .store import guard, lane, read_json, read_status, write


def requests(root, run):
    value = read_json(root / 'moves.json')
    if (type(value) is not dict or set(value) != {'version', 'run', 'requests'}
            or type(value['version']) is not int or value['version'] != 1 or value['run'] != run
            or type(value['requests']) is not list or len(value['requests']) > 1000):
        raise ValueError('Invalid attempt-control generation')
    seen = set()
    for row in value['requests']:
        if (type(row) is not dict or set(row) != {'id', 'attempt', 'target'}
                or any(type(row[k]) is not str for k in row)
                or not re.fullmatch('[0-9a-f]{32}', row['id'])
                or not re.fullmatch('[0-9a-f]{32}', row['attempt']) or row['attempt'] in seen):
            raise ValueError('Invalid or duplicate attempt-control request')
        seen.add(row['attempt'])
    return value


def move(repository, run, attempt, target, *, home=None):
    root = lane(repository, home)
    with guard(root):
        status = read_status(repository, home=home)
        if status is None or not status['active'] or status['run'] != run:
            raise ValueError('The selected test run is no longer active')
        value = requests(root, run)
        old = next((r for r in value['requests'] if r['attempt'] == attempt), None)
        if old is not None:
            if old['target'] != target:
                raise ValueError('This attempt already has a different target')
            return dict(run=run, request=old, acknowledged=False)
        active = status.get('attempts', {})
        if attempt not in active or active[attempt].get('state') != 'running':
            raise ValueError('The exact selected attempt is no longer running')
        if target not in status['capacities'] or status['desired'].get(target, 0) == 0:
            raise ValueError('Target host is not approved and enabled for this run')
        if len(value['requests']) >= 1000:
            raise ValueError('This run has reached the bounded operator request log size')
        row = dict(id=uuid.uuid4().hex, attempt=attempt, target=target)
        value['requests'].append(row)
        write(root / 'moves.json', value)
        return dict(run=run, request=row, acknowledged=False)
