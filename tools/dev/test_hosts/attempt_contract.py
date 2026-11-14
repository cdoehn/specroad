"""Move evidence adds cancelled attempts; final coverage stays exact and strict."""
from copy import deepcopy

from .contract import verify_live_pool


def verify_moves(observation, proof):
    actual = observation.get('host_pool')
    if type(actual) is not dict or actual.get('binding') != proof or actual.get('errors'):
        raise ValueError('Unbound move pool')
    cancellations = actual.get('cancellations')
    if type(cancellations) is not dict or set(cancellations) - actual.get('workers', {}).keys():
        raise ValueError('Invalid cancellation evidence')
    old = deepcopy(observation)
    pool = old['host_pool']
    tokens, cancelled, intervals = set(), {}, {}
    for name, row in pool['workers'].items():
        permits = pool['grants'].get(name, [])
        attempts = row.get('leases')
        if type(attempts) is not list or len(permits) != len(attempts):
            raise ValueError('Missing attempt grants')
        kept, grants = [], []
        for attempt, permit in zip(attempts, permits):
            is_cancelled = attempt.get('cancelled') is True
            expected = {'nodeid', 'slot', 'start', 'end', 'token'} | ({'cancelled'} if is_cancelled else set())
            if (set(attempt) != expected or set(permit) != {'index', 'slot', 'token'}
                    or not isinstance(attempt['token'], str) or len(attempt['token']) != 32
                    or attempt['token'] != permit['token'] or attempt['token'] in tokens):
                raise ValueError('Invalid or reused attempt identity')
            tokens.add(attempt['token'])
            intervals.setdefault((row['account'], attempt['slot']), []).append((attempt['start'], attempt['end']))
            if is_cancelled:
                record = cancellations.get(name)
                if (record is None or record.get('token') != attempt['token'] or record.get('target') not in pool['workers']
                        or record['target'] == name or record['receipt'].get('cancelled') is not True
                        or record['receipt'].get('children_remaining') != 0
                        or record['receipt'].get('binding') != {k: proof[k] for k in ('source_sha256', 'snapshot_sha256', 'environment_sha256')}):
                    raise ValueError('Restart has no complete source termination proof')
                receipt = record['receipt']['attempt']
                if any(receipt.get(k) != v for k, v in attempt.items() if k != 'cancelled'):
                    raise ValueError('Cancelled attempt differs from supervisor acknowledgement')
                if receipt.get('index') != permit['index'] or attempt['slot'] != permit['slot']:
                    raise ValueError('Cancelled permission mismatch')
                cancelled[(attempt['nodeid'], name)] = attempt['token']
                target = pool['workers'][record['target']]['leases']
                if not any(a['nodeid'] == attempt['nodeid'] for a in target):
                    raise ValueError('Cancelled test lacks a fresh target attempt')
            else:
                kept.append({k: v for k, v in attempt.items() if k != 'token'})
                grants.append({k: v for k, v in permit.items() if k != 'token'})
        row['leases'] = kept
        pool['grants'][name] = grants
    archive = observation.get('cancelled_attempts', [])
    if len(archive) != len(cancelled):
        raise ValueError('Cancelled outcomes are missing')
    for row in archive:
        if (cancelled.get((row['nodeid'], row['worker'])) != row['token']
                or any(v != 'passed' for v in row['phases'].values())):
            raise ValueError('A real failure or foreign attempt was replaced')
    for entries in intervals.values():
        ordered = sorted(entries)
        if any(a[0] > a[1] for a in ordered) or any(a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
            raise ValueError('Cancelled and fresh attempts overlap a shared host slot')
    verify_live_pool(old, proof)
