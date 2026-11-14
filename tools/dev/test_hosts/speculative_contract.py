"""Independent exact-coverage proof for authorized speculative attempts."""
from copy import deepcopy
import re

from .contract import verify_live_pool


def verify_copies(observation, proof):
    actual = observation.get('host_pool')
    if type(actual) is not dict or actual.get('binding') != proof or actual.get('errors'):
        raise ValueError('Unbound speculative pool')
    selected = actual.get('selected')
    if selected != observation.get('nodeids') or not isinstance(selected, list) or len(set(selected)) != len(selected):
        raise ValueError('Speculative collection changed')
    selected_set = set(selected)
    evidence = observation.get('copy_attempts')
    completions = observation.get('copy_completions')
    winners = observation.get('copy_winners')
    if type(evidence) is not list or type(completions) is not list or type(winners) is not dict:
        raise ValueError('Missing copy outcome evidence')
    records = {}
    for row in evidence:
        if (type(row) is not dict or set(row) != {'nodeid','worker','token','state','phases','worst'}
                or row['token'] in records or row['nodeid'] not in selected_set
                or row['state'] not in ('complete','cancelled')
                or row['worst'] not in ('not_run', 'passed') or type(row['phases']) is not dict
                or set(row['phases']) - {'setup','call','teardown'}
                or any(v != 'passed' for v in row['phases'].values())
                or row['state'] == 'complete' and row['phases'] != dict.fromkeys(('setup','call','teardown'), 'passed')):
            raise ValueError('Failed or unresolved copy outcome')
        records[row['token']] = row
    first, complete_tokens = {}, set()
    for entry in completions:
        if type(entry) is not dict or set(entry) != {'nodeid','worker','token'}:
            raise ValueError('Invalid copy completion order')
        row = records.get(entry['token'])
        if (row is None or row['state'] != 'complete' or any(row[k] != v for k,v in entry.items())
                or entry['token'] in complete_tokens):
            raise ValueError('Ambiguous copy completion')
        complete_tokens.add(entry['token'])
        first.setdefault(entry['nodeid'], entry['worker'])
    if (complete_tokens != {t for t,r in records.items() if r['state'] == 'complete'}
            or first != winners or set(first) != set(selected)):
        raise ValueError('Copy winner is not the first full completion')
    if observation.get('worker_test_counts') != {
            w: sum(owner == w for owner in winners.values()) for w in observation.get('workers', [])}:
        raise ValueError('Canonical coverage counted copies')
    cancelled = actual.get('cancellations')
    if type(cancelled) is not dict:
        raise ValueError('Missing copy termination evidence')
    archive = observation.get('cancelled_attempts', [])
    expected_archive = {t:r for t,r in records.items() if r['state'] == 'cancelled'}
    if (len(archive) != len(expected_archive) or {r['token'] for r in archive} != set(expected_archive)
            or set(cancelled) != {r['worker'] for r in expected_archive.values()}):
        raise ValueError('Cancelled outcomes differ from attempt ledger')
    for row in archive:
        record = expected_archive[row['token']]
        if any(row[k] != record[k] for k in ('nodeid','worker','phases')):
            raise ValueError('Cancellation lost phase evidence')
    expanded = deepcopy(observation)
    pool = expanded['host_pool']
    identities, counts, seen = [], {}, set()
    for name, row in pool['workers'].items():
        leases = row.get('leases')
        permits = pool['grants'].get(name, [])
        if type(leases) is not list or len(leases) != len(permits):
            raise ValueError('Missing copy lease or permission')
        counts[name] = len(leases)
        for lease, permit in zip(leases, permits):
            token = lease.get('token')
            is_cancelled = lease.get('cancelled') is True
            if (set(lease) != {'nodeid','slot','start','end','token'} | ({'cancelled'} if is_cancelled else set())
                    or type(token) is not str or not re.fullmatch('[0-9a-f]{32}', token)
                    or token in seen or token not in records
                    or set(permit) != {'index','slot','token'} or permit['token'] != token
                    or type(permit['index']) is not int or not 0 <= permit['index'] < len(selected)
                    or selected[permit['index']] != lease['nodeid'] or permit['slot'] != lease['slot']):
                raise ValueError('Foreign or repeated copy permission')
            record = records[token]
            if (record['nodeid'] != lease['nodeid'] or record['worker'] != name
                    or (record['state'] == 'cancelled') != is_cancelled):
                raise ValueError('Copy phases and lease differ')
            if is_cancelled:
                cancellation = cancelled.get(name, {})
                receipt = cancellation.get('receipt', {})
                target = cancellation.get('target')
                if (cancellation.get('token') != token or target == name or target not in actual['workers']
                        or receipt.get('cancelled') is not True or receipt.get('children_remaining') != 0
                        or receipt.get('binding') != {k:proof[k] for k in ('source_sha256','snapshot_sha256','environment_sha256')}
                        or any(receipt.get('attempt', {}).get(k) != v for k,v in lease.items() if k != 'cancelled')
                        or receipt['attempt'].get('index') != permit['index']):
                    raise ValueError('Loser lacks complete exact termination proof')
                if cancellation.get('reason') == 'copy':
                    if winners.get(lease['nodeid']) != target:
                        raise ValueError('Loser cancellation names no canonical winner')
                elif not any(r['worker'] == target and r['nodeid'] == lease['nodeid'] for r in records.values()):
                    raise ValueError('Move cancellation lacks its successor')
            seen.add(token)
            permit.clear()
            permit.update(index=len(identities), slot=lease['slot'])
            identities.append(token)
            lease['nodeid'] = token
            del lease['token']
            lease.pop('cancelled', None)
    if seen != set(records):
        raise ValueError('Attempt outcomes lack native leases')
    # The old strict resource/slot validator checks every attempt, including
    # cancelled and completed losers, before canonical coverage is accepted.
    pool['selected'] = identities
    expanded['nodeids'] = identities
    expanded['worker_test_counts'] = counts
    verify_live_pool(expanded, proof)
