"""Durable attempt lineage and explicit operator requests, without test retries."""
import json

import pytest

from dev.test_control.moves import move
from dev.test_control.store import Owner
from verification_support.outcomes import RunLedger
from verification_support.runtime_history import RuntimeHistory


def finish(history, run, node, worker):
    for phase in ('setup', 'call', 'teardown'):
        history.observe(run, node, node, worker, phase, 0.25, 'passed')


def test_cancelled_attempt_keeps_phases_and_requires_complete_fresh_target(tmp_path):
    node = 'tests/test_subject.py::test_one'
    with RuntimeHistory(tmp_path) as history:
        run = history.begin('a' * 64, 2)
        history.start(run, node, node, 'gw0', host='source', environment='b'*64)
        history.observe(run, node, node, 'gw0', 'setup', 0.125, 'passed')
        before = history.db.execute('SELECT * FROM phases').fetchall()
        phases = history.cancel(run, node, node, 'gw0', 'gw2', 'c'*32, '{}')
        assert phases == {'setup': 'passed'}
        assert history.snapshot([node])['tests'][0]['duration_ns'] is None
        history.start(run, node, node, 'gw2', host='target', environment='b'*64)
        with pytest.raises(ValueError, match='durable phases'):
            history.verify_run(run, {node: node}, {node: 'passed'})
        finish(history, run, node, 'gw2')
        history.verify_run(run, {node: node}, {node: 'passed'})
        assert history.db.execute('SELECT * FROM phases WHERE attempt=1').fetchall() == before
        assert history.db.execute('SELECT worker,invalid FROM attempts ORDER BY id').fetchall() == [('gw0', 1), ('gw2', 0)]
        assert history.db.execute('SELECT host FROM attempt_hosts ORDER BY attempt').fetchall() == [('source',), ('target',)]
        assert history.db.execute('PRAGMA foreign_key_check').fetchall() == []
        assert history.snapshot([node])['tests'][0]['duration_ns'] == 750_000_000


def test_cancelled_report_does_not_supply_final_coverage_or_hide_failure():
    ledger = RunLedger()
    ledger.collect('gw0', ['n'], [('n', 'identity')])
    ledger.observe('n', 'gw0', 'setup', 'passed')
    ledger.cancel('n', 'gw0', 'a'*32, {'setup': 'passed'})
    assert not ledger.result(0).wasSuccessful()
    for phase in ('setup', 'call', 'teardown'):
        ledger.observe('n', 'gw2', phase, 'passed')
    assert ledger.result(0).wasSuccessful()
    ledger.observe('n', 'gw0', 'call', 'failed')
    assert not ledger.result(0).wasSuccessful()
    assert 'cancelled_attempt_failed' in ledger.errors


def test_operator_request_is_exact_run_exact_attempt_and_idempotent(tmp_path):
    repository = tmp_path / 'apply'
    with_owner = Owner(repository, {'one': 1, 'two': 1}, {'one': 1, 'two': 1}, home=tmp_path/'private')
    try:
        token = 'a'*32
        with_owner.publish({}, attempts={token: dict(state='running', host='one', nodeid='n')})
        first = move(repository, with_owner.run, token, 'two', home=tmp_path/'private')
        assert move(repository, with_owner.run, token, 'two', home=tmp_path/'private') == first
        for run, attempt, target in [('other', token, 'two'), (with_owner.run, 'b'*32, 'two'), (with_owner.run, token, 'one')]:
            with pytest.raises(ValueError):
                move(repository, run, attempt, target, home=tmp_path/'private')
        assert len(json.loads((with_owner.root/'moves.json').read_text())['requests']) == 1
    finally:
        with_owner.close()
