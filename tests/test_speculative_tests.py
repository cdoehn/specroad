"""User-defined copy fairness, priority and independent durable measurements."""
import json
import sqlite3

import pytest

from dev.test_hosts.speculative_choice import choose
from dev.test_hosts.speculative_ledger import CopyLedger
from verification_support.runtime_history import RuntimeHistory


def rows(*values):
    return [dict(nodeid=node, host=host) for node, host in values]


def test_unstarted_queue_has_absolute_priority():
    assert choose('fast', {'fast','slow'}, rows(('one','slow')), waiting=True) is None


def test_minimum_global_copies_then_identity_without_speed_forecasts():
    active = rows(('a','one'), ('a','two'), ('b','one'), ('c','two'))
    assert choose('three', {'one','two','three'}, active) == 'b'
    active += rows(('b','three'))  # reservation counts before process starts
    assert choose('three', {'one','two','three'}, active) == 'c'


def test_hosts_are_covered_before_same_host_second_copy():
    active = rows(('a','one'))
    assert choose('one', {'one','two'}, active) is None
    assert choose('two', {'one','two'}, active) == 'a'
    active += rows(('a','two'))
    assert choose('one', {'one','two'}, active) is None
    assert choose('two', {'one','two'}, active) is None
    assert choose('disabled', {'one','two'}, active) is None


def start(history, run, worker, token, *, host=None):
    history.authorize_copy(run, 'node', worker, token)
    history.start(run, 'node', 'identity', worker, host=host or worker, environment='a'*64)


def phases(history, run, worker, seconds=1):
    for phase in ('setup','call','teardown'):
        history.observe(run, 'node', 'identity', worker, phase, seconds, 'passed')


def confirmation(token):
    return json.dumps(dict(cancelled=True, children_remaining=0, attempt=dict(token=token)))


def test_first_complete_winner_survives_newer_cancelled_copy_without_phase_mixing(tmp_path):
    with RuntimeHistory(tmp_path) as history:
        run = history.begin('a'*64, 2)
        history.enable_copies(run)
        start(history, run, 'gw0', 'a'*32)
        history.observe(run, 'node', 'identity', 'gw0', 'setup', 100, 'passed')
        start(history, run, 'gw1', 'b'*32)
        phases(history, run, 'gw1', 2)
        assert history.complete_copy(run, 'node', 'gw1', 'b'*32)
        assert history.snapshot(['identity'])['tests'][0]['duration_ns'] is None
        history.cancel_copy(run, 'node', 'identity', 'gw0', 'a'*32, confirmation('a'*32))
        history.verify_run(run, {'node':'identity'}, {'identity':'passed'})
        assert history.snapshot(['identity'])['tests'][0]['duration_ns'] == 6_000_000_000
        assert history.db.execute('SELECT COUNT(*) FROM phases').fetchone() == (4,)
        assert history.db.execute('SELECT worker,invalid,complete FROM attempts ORDER BY id').fetchall() == [('gw0',1,0),('gw1',0,1)]
        assert history.db.execute('PRAGMA foreign_key_check').fetchall() == []


def test_same_run_duplicates_need_independent_exact_reservations(tmp_path):
    with RuntimeHistory(tmp_path) as history:
        run = history.begin('a'*64, 2)
        history.enable_copies(run)
        start(history, run, 'gw0', 'a'*32)
        with pytest.raises(ValueError):
            history.start(run, 'node', 'identity', 'gw1')
        with pytest.raises((ValueError, sqlite3.IntegrityError)):
            history.start(run, 'node', 'identity', 'gw0')


def test_canonical_coverage_is_once_and_loser_failure_stays_red():
    ledger = CopyLedger()
    ledger.collect('gw0', ['node'], [('node','identity')])
    for worker, token in [('gw0','a'*32),('gw1','b'*32)]:
        ledger.authorize('node', worker, token)
    for phase in ('setup','call','teardown'):
        ledger.observe('node','gw1',phase,'passed')
    assert ledger.completed('node','gw1','b'*32)
    ledger.cancel('node','gw0','a'*32, {'setup':'passed','call':'failed'})
    result = ledger.snapshot(0)
    assert result['tests_run'] == 1 and not result['suite_passed']
    assert result['worker_test_counts'] == {'gw0':0, 'gw1':1}
    assert result['test_outcomes']['identity'] == 'failed'
