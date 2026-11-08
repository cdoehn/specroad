"""Phase validity, source boundaries and independent refresh, never TUI layout."""
import json
import os
from pathlib import Path
import sqlite3
import threading

import pytest

from dev.status import monitor, monitor_data
from dev.status.runtime_read import connection
from test_runtime_history import complete
from test_status_helpers import digest
from test_test_monitor import invoke_monitor, monitor_lane
from verification_support.runtime_history import RuntimeHistory


def test_monitor_failed_latest_attempt_retains_its_phases_without_old_success(tmp_path):
    dev, apply, database, lock = monitor_lane(tmp_path)
    with RuntimeHistory(tmp_path / 'storage', path=database) as store:
        run = store.begin('b' * 64, 1)
        complete(store, run, 'merge.slow', seconds=2, failure='call')
        store.finish(run, 1)
    before = digest(database)
    code, report = invoke_monitor(dev, tmp_path, '--match', 'merge')
    assert code == 0
    row = report['repositories'][0]['history']['data']['tests'][0]
    assert row['total_seconds'] == 6 and row['status'] == 'failed'
    assert row['completed'] and row['measurement_complete'] and not row['valid_measurement']
    assert row['phase_outcomes'] == {'setup': 'passed', 'call': 'failed', 'teardown': 'passed'}
    # The completed Apply run remains the a-source run, independent of history.
    assert report['repositories'][0]['status']['data']['run']['source'] == 'a' * 64
    assert digest(database) == before


def test_baseline_has_only_total_and_new_attempt_suppresses_it(tmp_path):
    # Native schema, with a minimal imported seed; no fabricated phase rows.
    with RuntimeHistory(tmp_path) as store:
        with store.db:
            store.db.execute('INSERT INTO origins VALUES(?,?)', ('a' * 64, '{}'))
            store.db.execute('INSERT INTO seeds(test,duration,origin) VALUES(?,?,?)', ('seed', 7_000_000_000, 'a' * 64))
        database = store.path
    row, = monitor_data.history(database)
    assert row['origin'] == 'baseline' and row['total_seconds'] == 7
    assert row['completed'] is None and row['measurement_complete'] is False
    assert row['setup_seconds'] is row['call_seconds'] is row['teardown_seconds'] is None
    with RuntimeHistory(tmp_path) as store:
        store.start(store.begin('b' * 64, 1), 'tests/test_sample.py::seed', 'seed', 'gw0')
    row, = monitor_data.history(database)
    assert row['origin'] == 'attempt' and row['total_seconds'] is None and not row['valid_measurement']


@pytest.mark.parametrize('fault', ['duration', 'phase', 'outcome', 'started', 'metadata'])
def test_monitor_rejects_corrupt_latest_measurements_without_reusing_old_data(tmp_path, fault):
    dev, apply, database, lock = monitor_lane(tmp_path)
    with sqlite3.connect(database) as db:
        if fault == 'duration':
            db.execute('UPDATE phases SET duration=-1 WHERE phase="call"')
        elif fault == 'phase':
            db.execute('UPDATE phases SET phase="unknown" WHERE phase="call"')
        elif fault == 'outcome':
            db.execute('UPDATE phases SET outcome="unknown" WHERE phase="call"')
        elif fault == 'started':
            db.execute('UPDATE attempts SET started="no-date"')
        else:
            db.execute('UPDATE metadata SET version=99')
    before = digest(database)
    code, report = invoke_monitor(dev, tmp_path)
    assert code == 2 and report['repositories'][0]['history']['stale']
    assert report['repositories'][0]['history']['data']['tests'] == []
    assert digest(database) == before


def test_monitor_blocks_foreign_default_database_until_writer_policy_is_migrated(tmp_path):
    first, apply, one, lock = monitor_lane(tmp_path)
    second, apply2, two, lock2 = monitor_lane(tmp_path, '2', 20)
    policy = apply2 / 'verification/test_runtime_policy.json'
    value = json.loads(policy.read_text())
    value['database'] = '../exchange/specroad-test-runtime-history.sqlite3'
    policy.write_text(json.dumps(value))
    code, report = invoke_monitor(second, tmp_path)
    assert code == 0
    history = report['repositories'][0]['history']['data']
    assert history['status'] == 'configuration_pending' and history['tests'] == []
    code, report = invoke_monitor(second, tmp_path, '--database', str(one))
    assert code == 0 and report['repositories'][0]['history']['data']['database_explicit']
    assert report['repositories'][0]['history']['data']['tests'][0]['total_seconds'] == 30


def test_phase_query_rejects_different_run_identity(tmp_path):
    with RuntimeHistory(tmp_path) as store:
        run = store.begin('a' * 64, 1)
        complete(store, run)
        database = store.path
        started = store.db.execute('SELECT started FROM runs WHERE id=?', (run,)).fetchone()[0]
    with pytest.raises(ValueError):
        monitor_data.run_tests(database, {'id': run, 'source': 'b' * 64, 'started': started})


def test_monitor_rejects_measurements_with_foreign_catalog_identity(tmp_path):
    dev, apply, database, lock = monitor_lane(tmp_path)
    catalog = apply / 'build/apply-1-local/W/gate/catalog.json'
    value = json.loads(catalog.read_text())
    value['nodeid_to_test_id'] = {k: 'foreign.' + v for k, v in value['nodeid_to_test_id'].items()}
    catalog.write_text(json.dumps(value))
    code, report = invoke_monitor(dev, tmp_path)
    assert code == 2 and report['repositories'][0]['status']['stale']
    assert report['repositories'][0]['status']['data']['tests'] == []


@pytest.mark.skipif(os.name != 'posix', reason='FIFO observation on POSIX')
def test_nonregular_progress_is_rejected_without_blocking_or_claiming_free(tmp_path):
    dev, apply, database, lock = monitor_lane(tmp_path)
    path = apply / 'build/apply-1-local/progress-0002.json'
    os.mkfifo(path)
    code, report = invoke_monitor(dev, tmp_path)
    assert code == 2
    assert report['repositories'][0]['status']['data']['report']['availability']['state'] == 'unknown'
    assert path.is_fifo()


def test_readonly_query_enforces_deadline_and_cannot_write(tmp_path):
    with RuntimeHistory(tmp_path) as store:
        database = store.path
    before = digest(database)
    with connection(database, timeout=0.01) as db:
        with pytest.raises(sqlite3.OperationalError):
            db.execute('UPDATE metadata SET version=2')
        with pytest.raises(sqlite3.OperationalError):
            db.execute('WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<1000000000) SELECT sum(x) FROM n').fetchone()
    assert digest(database) == before


def test_locked_database_is_reported_per_source_without_writing_or_hiding_peer(tmp_path):
    dev, apply, database, lock = monitor_lane(tmp_path)
    second, apply2, two, lock2 = monitor_lane(tmp_path, '2', 20)
    before = digest(database)
    db = sqlite3.connect(database)
    try:
        db.execute('BEGIN EXCLUSIVE')
        code, report = invoke_monitor(dev, tmp_path, '--all', '--query-timeout', '0.1')
    finally:
        db.rollback()
        db.close()
    assert code == 2
    first, other = report['repositories']
    assert first['history']['stale'] and not other['history']['stale']
    assert other['status']['data']['report']['status'] == 'completed'
    assert digest(database) == before


def test_independent_refresh_exposes_fast_sources_while_one_is_still_reading(tmp_path, monkeypatch):
    slow, fast = tmp_path / 'slow', tmp_path / 'fast'
    entered, release = threading.Event(), threading.Event()

    def status(path, *_):
        if path == slow:
            entered.set()
            assert release.wait(5)
        return {'report': {'status': 'completed'}, 'tests': []}

    monkeypatch.setitem(monitor.COLLECTORS, 'status', status)
    monkeypatch.setitem(monitor.COLLECTORS, 'history', lambda *_: {'status': 'ok', 'tests': []})
    refresh = monitor.Refresh([slow, fast])
    try:
        refresh.request()
        assert entered.wait(2)
        refresh.entries[(str(fast), 'status')]['future'].result(timeout=2)
        refresh.harvest()
        result = refresh.snapshot()
        assert result[1]['status']['data']['report']['status'] == 'completed'
        assert result[0]['status']['refreshing'] and result[0]['status']['data'] is None
        current = refresh.entries[(str(slow), 'status')]['future']
        refresh.request(force=True)
        assert refresh.entries[(str(slow), 'status')]['future'] is current
    finally:
        release.set()
        refresh.pool.shutdown(wait=True, cancel_futures=True)


def test_refresh_preserves_last_snapshot_marks_stale_and_recovers(tmp_path, monkeypatch):
    responses = iter([{'report': {'status': 'completed'}, 'tests': []},
                      {'report': {'status': 'unavailable', 'error': 'read failure'}, 'tests': []},
                      {'report': {'status': 'running'}, 'tests': []}])
    monkeypatch.setitem(monitor.COLLECTORS, 'status', lambda *_: next(responses))
    monkeypatch.setitem(monitor.COLLECTORS, 'history', lambda *_: {'status': 'ok', 'tests': []})
    refresh = monitor.Refresh([tmp_path])
    try:
        snapshots = []
        for _ in range(3):
            refresh.request(force=True)
            for state in refresh.entries.values():
                state['future'].result(timeout=2)
            refresh.harvest()
            snapshots.append(refresh.snapshot()[0]['status'])
        assert snapshots[0]['data']['report']['status'] == 'completed' and not snapshots[0]['stale']
        assert snapshots[1]['data']['report']['status'] == 'completed' and snapshots[1]['stale']
        assert snapshots[1]['error'] == 'read failure'
        assert snapshots[2]['data']['report']['status'] == 'running' and not snapshots[2]['stale']
    finally:
        refresh.pool.shutdown(wait=True, cancel_futures=True)


def test_monitor_invalid_once_options_return_machine_error_without_creating_sources(tmp_path):
    dev, apply, database, lock = monitor_lane(tmp_path)
    before = digest(database)
    for args in (('--query-timeout', 'nan'), ('--query-timeout', '31'), ('--interval', '0'),
                 ('--limit', '-1'), ('--database', str(tmp_path / 'missing.sqlite3'))):
        code, report = invoke_monitor(dev, tmp_path, *args)
        assert code == 2
        assert report.get('status') == 'unavailable' or report['repositories'][0]['status']['stale']
    assert not (tmp_path / 'missing.sqlite3').exists() and digest(database) == before


@pytest.mark.parametrize('view', ['total', 'phases', 'both'])
def test_machine_phase_values_are_independent_of_time_view(tmp_path, view):
    dev, apply, database, lock = monitor_lane(tmp_path)
    code, report = invoke_monitor(dev, tmp_path, '--time-view', view, '--limit', '1')
    assert code == 0
    data = report['repositories'][0]['history']['data']
    assert data['matching_tests'] == 2 and data['truncated']
    row = data['tests'][0]
    assert [row[p + '_seconds'] for p in ('setup', 'call', 'teardown', 'total')] == [10, 10, 10, 30]


def test_history_read_limit_is_an_explicit_error_not_partial_measurement(tmp_path, monkeypatch):
    dev, apply, database, lock = monitor_lane(tmp_path)
    before = digest(database)
    monkeypatch.setattr(monitor_data, 'MAX_PHASE_ROWS', 1)
    with pytest.raises(ValueError):
        monitor_data.history(database)
    assert digest(database) == before
