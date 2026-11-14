"""Attempt migration races, failure retention and bounded independent operators."""
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3

import pytest

from dev.test_control.moves import move
from dev.test_control.store import Owner
from verification_support.runtime_history import RuntimeHistory
from test_test_control_move import finish


@pytest.mark.parametrize('phase', ['setup', 'call', 'teardown', 'subtest'])
def test_real_failure_cannot_be_replaced_in_durable_history(tmp_path, phase):
    with RuntimeHistory(tmp_path) as history:
        run = history.begin('a'*64, 2)
        node = 'tests/test_subject.py::test_one'
        history.start(run, node, node, 'gw0')
        if phase == 'subtest':
            history.observe(run, node, node, 'gw0', 'call', .1, 'failed', subtest=True)
        else:
            for part in ('setup', 'call', 'teardown'):
                history.observe(run, node, node, 'gw0', part, .1, 'failed' if part == phase else 'passed')
                if part == phase:
                    break
        with pytest.raises(ValueError, match='Failed|failure'):
            history.cancel(run, node, node, 'gw0', 'gw2', 'b'*32, '{}')
        with pytest.raises(sqlite3.IntegrityError):
            history.start(run, node, node, 'gw2')
        assert history.snapshot([node])['tests'][0]['duration_ns'] is None


def test_two_confirmed_moves_preserve_chain_and_reject_late_failure(tmp_path):
    with RuntimeHistory(tmp_path) as history:
        run = history.begin('a'*64, 3)
        node = 'tests/test_subject.py::test_one'
        history.start(run, node, node, 'gw0')
        history.cancel(run, node, node, 'gw0', 'gw2', 'b'*32, '{}')
        history.start(run, node, node, 'gw2')
        history.cancel(run, node, node, 'gw2', 'gw4', 'c'*32, '{}')
        history.start(run, node, node, 'gw4')
        finish(history, run, node, 'gw4')
        history.verify_run(run, {node:node}, {node:'passed'})
        history.observe(run, node, node, 'gw0', 'setup', .1, 'error')
        with pytest.raises(ValueError, match='lineage'):
            history.verify_run(run, {node:node}, {node:'passed'})


@pytest.mark.parametrize('fault', ['worker', 'identity', 'run', 'successor', 'phase'])
def test_foreign_successor_cannot_complete_cancelled_attempt(tmp_path, fault):
    with RuntimeHistory(tmp_path) as history:
        run = history.begin('a'*64, 2); node = 'tests/test_subject.py::test_one'
        history.start(run, node, node, 'gw0')
        history.cancel(run, node, node, 'gw0', 'gw2', 'b'*32, '{}')
        if fault in ('worker', 'identity'):
            with pytest.raises(sqlite3.IntegrityError):
                history.start(run, node, 'foreign' if fault == 'identity' else node, 'gw9' if fault == 'worker' else 'gw2')
            return
        history.start(run, node, node, 'gw2'); finish(history, run, node, 'gw2')
        if fault == 'successor':
            history.db.execute('UPDATE attempt_moves SET successor=NULL')
        elif fault == 'run':
            other = history.begin('b'*64, 1)
            history.db.execute('UPDATE attempts SET run=? WHERE worker=?', (other, 'gw2'))
        else:
            history.db.execute("DELETE FROM phases WHERE attempt=2 AND phase='teardown'")
            history.db.execute('UPDATE attempts SET complete=0 WHERE id=2')
        history.db.commit()
        with pytest.raises(ValueError):
            history.verify_run(run, {node:node}, {node:'passed'})


def test_repeated_parallel_move_commands_are_one_request_and_cannot_cross_lanes(tmp_path):
    home = tmp_path/'private'
    one = Owner(tmp_path/'apply', {'host': 1}, {'host': 1}, home=home)
    two = Owner(tmp_path/'apply2', {'host': 1}, {'host': 1}, home=home)
    try:
        token = 'a'*32
        one.publish({}, attempts={token: dict(state='running', host='host', nodeid='n')})
        with ThreadPoolExecutor(max_workers=4) as executor:
            values = list(executor.map(lambda _: move(tmp_path/'apply', one.run, token, 'host', home=home), range(8)))
        assert all(value == values[0] for value in values)
        with pytest.raises(ValueError):
            move(tmp_path/'apply2', one.run, token, 'host', home=home)
        assert json.loads((two.root/'moves.json').read_text())['requests'] == []
    finally:
        one.close(); two.close()


def test_monitor_keeps_cancelled_attempt_and_ranks_only_new_complete_measurement(tmp_path):
    from dev.status.monitor_data import run_tests
    from dev.status.test_time import ranking
    with RuntimeHistory(tmp_path) as history:
        run = history.begin('a'*64, 2); node = 'tests/test_subject.py::test_one'
        history.start(run, node, node, 'gw0', host='one', environment='c'*64)
        history.observe(run, node, node, 'gw0', 'setup', 15, 'passed')
        history.cancel(run, node, node, 'gw0', 'gw2', 'b'*32, '{}')
        history.start(run, node, node, 'gw2', host='two', environment='c'*64)
        finish(history, run, node, 'gw2')
        history.db.row_factory = sqlite3.Row
        bound = dict(history.db.execute('SELECT * FROM runs WHERE id=?', (run,)).fetchone())
        rows, _ = run_tests(history.path, bound)
        assert [(r['host'], r['status']) for r in rows] == [('one','cancelled'), ('two','passed')]
        assert rows[0]['elapsed_seconds'] is None and not rows[0]['valid_measurement']
        result = ranking(history.path)
        assert result['tests'][0]['duration_ns'] == 750_000_000
