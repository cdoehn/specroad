"""Competing writers cannot overtake a validated live attempt or its phase."""
import sqlite3

import pytest

from verification_support import runtime_attempts
from verification_support.runtime_history import RuntimeHistory


def test_competing_finish_cannot_overtake_the_live_check_of_a_new_attempt(tmp_path, monkeypatch):
    with RuntimeHistory(tmp_path) as store, RuntimeHistory(tmp_path) as competing:
        competing.db.execute('PRAGMA busy_timeout=0')
        run = store.begin('a' * 64, 2)
        original = runtime_attempts.start_allowed
        observations = []

        def interleave(db, current_run, node, identity, worker):
            # This is the real second writer, after the first has checked the
            # live run and before it inserts its durable attempt. No retry.
            with pytest.raises(sqlite3.OperationalError, match='locked'):
                competing.finish(run, 0)
            observations.append(competing.db.execute('SELECT finished FROM runs WHERE id=?', (run,)).fetchone())
            return original(db, current_run, node, identity, worker)

        with monkeypatch.context() as patch:
            patch.setattr(runtime_attempts, 'start_allowed', interleave)
            store.start(run, 'node', 'case', 'gw0')
        assert observations == [(None,)]
        assert competing.db.execute('SELECT node,test,worker FROM attempts').fetchall() == [('node', 'case', 'gw0')]
        competing.finish(run, 0)
        with pytest.raises(ValueError, match='unfinished run'):
            store.start(run, 'other', 'other-case', 'gw1')
        assert competing.db.execute('SELECT COUNT(*) FROM attempts').fetchone() == (1,)


def test_phase_validation_and_persistence_exclude_a_competing_writer(tmp_path):
    with RuntimeHistory(tmp_path) as store, RuntimeHistory(tmp_path) as competing:
        competing.db.execute('PRAGMA busy_timeout=0')
        run = store.begin('a' * 64, 2)
        store.start(run, 'node', 'case', 'gw0')
        observations = []

        def interleave(statement):
            # Trace observes native SQL; callback exceptions are not used as
            # a pytest oracle. Record whether a real concurrent finish wins.
            if statement.lstrip().upper().startswith('SELECT') and not observations:
                try:
                    competing.finish(run, 0)
                except sqlite3.OperationalError as error:
                    observations.append(str(error))
                else:
                    observations.append('competing writer committed')

        store.db.set_trace_callback(interleave)
        try:
            store.observe(run, 'node', 'case', 'gw0', 'setup', 0.25, 'passed')
        finally:
            store.db.set_trace_callback(None)
        assert len(observations) == 1 and 'locked' in observations[0]
        assert competing.db.execute('SELECT phase,duration,outcome FROM phases').fetchall() == [('setup', 250000000, 'passed')]
        assert store.snapshot(['case'])['tests'][0]['duration_ns'] is None
        for phase in ('call', 'teardown'):
            store.observe(run, 'node', 'case', 'gw0', phase, 0.25, 'passed')
        competing.finish(run, 0)
        assert store.snapshot(['case'])['tests'][0]['duration_ns'] == 750000000


def test_rejected_attempt_releases_its_transaction_without_creating_evidence(tmp_path):
    with RuntimeHistory(tmp_path) as store, RuntimeHistory(tmp_path) as competing:
        competing.db.execute('PRAGMA busy_timeout=0')
        run = store.begin('a' * 64, 2)
        store.start(run, 'node', 'case', 'gw0')
        with pytest.raises(sqlite3.IntegrityError):
            store.start(run, 'node', 'case', 'gw1')
        assert not store.db.in_transaction
        other = competing.begin('b' * 64, 2)
        competing.start(other, 'other', 'other-case', 'gw1')
        assert competing.db.execute('SELECT COUNT(*) FROM attempts').fetchone() == (2,)
        assert competing.db.execute('SELECT COUNT(*) FROM phases').fetchone() == (0,)
        assert all(row['duration_ns'] is None for row in store.snapshot(['case', 'other-case'])['tests'])
