"""Measurement semantics and deterministic queries, independent of terminal views."""
from . import apply_status

PHASES = ('setup', 'call', 'teardown')


def phase_rows(rows, run, now):
    attempts = {}
    for row in rows:
        if (any(type(row[k]) is not int or row[k] < 1 for k in ('id', 'run'))
                or any(not isinstance(row[k], str) or not row[k] for k in ('test', 'node', 'worker', 'started'))
                or row['invalid'] not in (0, 1) or row['complete'] not in (0, 1)):
            raise ValueError('Ungültiger Laufzeitversuch')
        apply_status.stamp(row['started'])
        item = attempts.setdefault(row['id'], {**dict(row), 'phases': {}})
        if row['phase'] is not None:
            if row['phase'] not in PHASES or row['phase'] in item['phases']:
                raise ValueError('Unbekannte oder doppelte Messphase')
            if type(row['duration']) is not int or not 0 <= row['duration'] <= 86_400_000_000_000:
                raise ValueError('Ungültige Phasendauer')
            if row['outcome'] not in ('passed', 'failed', 'error', 'unexpected_success', 'skipped', 'expected_failure'):
                raise ValueError('Unbekanntes Phasenergebnis')
            apply_status.stamp(row['recorded'])
            item['phases'][row['phase']] = dict(row)
    result = []
    for item in attempts.values():
        phases = item['phases']
        durations = {phase + '_seconds': phases[phase]['duration'] / 1e9
                     if phase in phases else None for phase in PHASES}
        complete = len(phases) == 3
        terminal = 'teardown' in phases
        outcomes = {row['outcome'] for row in phases.values()}
        valid = complete and item['complete'] == 1 and item['invalid'] == 0 and outcomes == {'passed'}
        if outcomes & {'failed', 'error', 'unexpected_success'}:
            status = 'failed'
        elif outcomes & {'skipped', 'expected_failure'}:
            status = 'skipped'
        elif valid:
            status = 'passed'
        elif terminal or item['invalid']:
            status = 'invalid'
        else:
            status = 'unfinished'
        active = None if terminal else 'teardown' if 'call' in phases else 'call' if 'setup' in phases else 'setup'
        finish = (run or {}).get('finished')
        elapsed = max(0, (apply_status.stamp(finish) if finish else now) - apply_status.stamp(item['started']))
        result.append({'test_name': item['test'], 'nodeid': item['node'],
            'host': item.get('host'), 'environment_sha256': item.get('environment'),
            'worker': item['worker'], 'run_id': item['run'], 'attempt_id': item['id'],
            'origin': 'attempt', 'started_at': item['started'], 'status': status,
            'completed': terminal, 'measurement_complete': complete, 'valid_measurement': valid,
            'phase': active, 'phase_outcomes': {p: phases[p]['outcome'] if p in phases else None for p in PHASES},
            **durations, 'total_seconds': sum(durations.values()) if complete else None,
            'elapsed_seconds': elapsed if not terminal else None})
    return result


def filtered(rows, *, match='', minimum=0, sort='total', descending=True, limit=200):
    """Filter before limiting; stable name ties; unknown durations always last."""
    key = sort + '_seconds'
    minimum_key = 'total_seconds' if sort == 'name' else key
    matches = [r for r in rows if match.casefold() in (r['test_name'] + ' ' + (r.get('nodeid') or '') + ' ' + (r.get('host') or '')).casefold()
               and (minimum == 0 or r.get(minimum_key) is not None and r[minimum_key] >= minimum)]
    matches.sort(key=lambda r: r['test_name'])
    if sort == 'name':
        if descending:
            matches.reverse()
    else:
        known = [r for r in matches if r.get(key) is not None]
        unknown = [r for r in matches if r.get(key) is None]
        known.sort(key=lambda r: r[key], reverse=descending)
        matches = known + unknown
    return matches[:limit] if limit else matches, len(matches)
