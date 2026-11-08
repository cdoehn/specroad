"""Independent Apply observations and phase measurements for the test monitor.

No product imports, test execution, registration or writer-policy changes.
Public durations are seconds; unknown values stay None, including baselines'
phase components. Elapsed wall time is never a measured phase duration.
"""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import time

from . import apply_status
from .cli import Target
from .runtime_read import connection
from .test_time import current_tests
from .monitor_times import PHASES, phase_rows, filtered

READ_ERRORS = (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError, OverflowError, sqlite3.Error)
MAX_PHASE_ROWS = 300000


def targets(repository, directories=(), *, all_targets=False, database=None):
    """Explicit paths or this workspace's Apply lanes, deduplicated by real path."""
    if all_targets and directories:
        raise ValueError('--all und --apply-dir sind alternative Zielauswahlen.')
    repository = Path(repository).resolve()
    if all_targets:
        workspace = repository.parent
        paths = [workspace / 'specroad-apply', workspace / 'specroad-apply2']
        paths += sorted((p for p in workspace.glob('specroad-apply*') if p.is_dir()), key=str)
    elif directories:
        paths = list(directories)
    else:
        paths = [Target.from_repository(repository).repository]
    paths = list(dict.fromkeys(Path(p).expanduser().resolve() for p in paths))
    if database is not None and len(paths) != 1:
        raise ValueError('--database ist nur für genau ein Apply-Ziel zulässig.')
    if len(paths) > 16:
        raise ValueError('Höchstens 16 Apply-Ziele gleichzeitig auswählen.')
    return paths


def observed():
    return datetime.now(timezone.utc).isoformat()


def unavailable(repository, error):
    """Keep positive busy evidence even if unrelated status input is broken."""
    proc = apply_status.process_view(repository)
    availability = apply_status.repository_availability(repository, proc['processes'])
    if not repository.is_dir():
        availability.update(state='missing', reason='directory_missing')
    elif availability['state'] == 'free':
        availability.update(state='unknown', reason='status_unreadable')
    return {'repository': str(repository), 'target': repository.name,
            'status': 'unavailable', 'error': str(error), 'warnings': [],
            'observed_at': time.time(), 'stages': [], 'tests': None, 'bundle': None,
            'availability': availability,
            'processes': proc}


SELECT_PHASES = '''SELECT a.id,a.run,a.node,a.test,a.worker,a.started,a.invalid,a.complete,
                         p.phase,p.duration,p.outcome,p.recorded
                  FROM attempts a LEFT JOIN phases p ON p.attempt=a.id'''


def bounded_rows(cursor):
    rows = cursor.fetchmany(MAX_PHASE_ROWS + 1)
    if len(rows) > MAX_PHASE_ROWS:
        raise ValueError('Laufzeitquelle überschreitet das Leselimit; keine Teilmessung ausgegeben.')
    return rows


def run_tests(database, expected_run, timeout=5):
    """Only the run already bound to the Apply gate, never the globally newest run."""
    with connection(database, timeout) as db:
        run = db.execute('SELECT * FROM runs WHERE id=?', (expected_run['id'],)).fetchone()
        if run is None or any(run[k] != expected_run[k] for k in ('id', 'source', 'started')):
            raise ValueError('Laufzeitquelle hat ihre Apply-Laufbindung gewechselt.')
        rows = bounded_rows(db.execute(SELECT_PHASES + ' WHERE a.run=? ORDER BY a.id', (run['id'],)))
        return phase_rows(rows, dict(run), time.time()), dict(run)


def collect_status(repository, database=None, timeout=5):
    try:
        view = apply_status.collect(repository, apply_directory=repository, database=database, query_timeout=timeout)
        rows, run = [], None
        if view.get('tests') and view['tests'].get('run'):
            bundle = Path(view['report_directory'])
            progress, checkpoint = apply_status.progress_at(bundle)
            if checkpoint.stat().st_mtime != view.get('progress_updated_at'):
                raise ValueError('Apply wechselte während der Statusabfrage die Stage.')
            gate = bundle / view['test_commit'] / 'gate'
            catalog = apply_status.read_json(gate / 'catalog.json')
            if catalog.get('catalog_valid') is not True or catalog.get('collection_exit_code') != 0:
                raise ValueError('Unvollständige oder ungültige Apply-Collection')
            pairs = catalog['nodeid_to_test_id']
            nodes = apply_status.capture_native_file(gate / 'nodeids.txt', 16_000_000).decode('utf-8').splitlines()
            if not nodes or len(nodes) != len(set(nodes)) or not set(nodes) <= pairs.keys():
                raise ValueError('Ungültige native Apply-Testauswahl')
            rows, run = run_tests(Path(view['database']), view['tests']['run'], timeout)
            selected_nodes = set(nodes)
            if any(r['nodeid'] not in selected_nodes or pairs.get(r['nodeid']) != r['test_name'] for r in rows):
                raise ValueError('Messphasen passen nicht zur gebundenen Apply-Testauswahl.')
            if apply_status.progress_at(bundle)[1] != checkpoint:
                raise ValueError('Apply wechselte während der Phasenabfrage die Stage.')
        return {'observed_at': observed(), 'report': view, 'tests': rows, 'run': run}
    except READ_ERRORS as error:
        return {'observed_at': observed(), 'report': unavailable(repository, error), 'tests': [], 'run': None}


def history(database, identities=None, timeout=5):
    """Latest started attempts suppress all older success, even when unfinished."""
    with connection(database, timeout) as db:
        rows = bounded_rows(db.execute(SELECT_PHASES + '''
            WHERE a.id IN (SELECT MAX(id) FROM attempts GROUP BY test) ORDER BY a.id'''))
        result = phase_rows(rows, None, time.time())
        attempted = {row['test_name'] for row in result}
        seeds = bounded_rows(db.execute('SELECT test,duration FROM seeds WHERE id IN (SELECT MAX(id) FROM seeds GROUP BY test)'))
        for row in seeds:
            if row['test'] in attempted:
                continue
            if not isinstance(row['test'], str) or not row['test'] or type(row['duration']) is not int or row['duration'] < 0:
                raise ValueError('Ungültige Baseline-Dauer')
            result.append({'test_name': row['test'], 'nodeid': None, 'worker': None,
                'run_id': None, 'attempt_id': None, 'origin': 'baseline', 'started_at': None,
                'status': 'baseline', 'completed': None, 'measurement_complete': False,
                'valid_measurement': True, 'phase': None, 'phase_outcomes': dict.fromkeys(PHASES),
                **{p + '_seconds': None for p in PHASES},
                'total_seconds': row['duration'] / 1e9, 'elapsed_seconds': None})
    # Historical unfinished attempts are not live clocks. Elapsed time belongs
    # only to the separately bound current Apply run.
    for row in result:
        row['elapsed_seconds'] = None
    if identities is not None:
        result = [row for row in result if row['test_name'] in identities]
    return result


def collect_history(repository, database=None, timeout=5):
    value = {'observed_at': observed(), 'status': 'ok', 'warnings': [], 'tests': []}
    try:
        selected = Target.from_repository(repository, apply_directory=repository, database=database)
        value.update(selected.metadata())
        ready, warning = selected.runtime_ready()
        if warning:
            value['warnings'].append(warning)
        if not ready:
            value['status'] = 'configuration_pending'
            return value
        identities, catalog = current_tests(repository)
        value['collection'] = catalog
        if not selected.database.is_file():
            value['status'] = 'no_history'
            return value
        value['tests'] = history(selected.database, identities, timeout)
        value['known_tests'] = len(identities) if identities is not None else len(value['tests'])
        value['valid_measurements'] = sum(row['valid_measurement'] for row in value['tests'])
        value['without_valid_measurement'] = value['known_tests'] - value['valid_measurements']
    except READ_ERRORS as error:
        value.update(status='unavailable', error=str(error))
    return value
