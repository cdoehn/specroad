"""Missing local identity, atomic writes and complete host-bound evidence."""
import sqlite3

import pytest

from verification_support import local_history
from verification_support.runtime_history import RuntimeHistory, LOCAL
from test_runtime_history import complete


@pytest.mark.parametrize('hostname', ['', ' ', ' host', 'host ', 'two hosts', 'host\nline', '\x1bhost', 'x' * 256, None])
def test_invalid_local_identity_creates_no_runtime_history(tmp_path, monkeypatch, hostname):
    monkeypatch.setattr(local_history.platform, 'node', lambda: hostname)
    with pytest.raises(ValueError):
        local_history.LocalRuntimeHistory(tmp_path)
    assert not (tmp_path / LOCAL).exists()


def test_environment_capture_failure_cannot_become_unknown_host_success(tmp_path, monkeypatch):
    def unavailable():
        raise OSError('synthetic environment unavailable')
    monkeypatch.setattr(local_history, 'environment', unavailable)
    with pytest.raises(OSError):
        local_history.LocalRuntimeHistory(tmp_path)
    assert not (tmp_path / LOCAL).exists()


def test_host_write_failure_rolls_back_the_whole_new_attempt(tmp_path):
    with local_history.LocalRuntimeHistory(tmp_path) as store:
        run = store.begin('a' * 64, 1)
        store.db.set_authorizer(lambda action, table, *rest: sqlite3.SQLITE_DENY
                                if action == sqlite3.SQLITE_INSERT and table == 'attempt_hosts' else sqlite3.SQLITE_OK)
        with pytest.raises(sqlite3.DatabaseError):
            store.start(run, 'node', 'identity', 'gw0')
        store.db.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
        assert store.db.execute('SELECT COUNT(*) FROM attempts').fetchone() == (0,)
        assert store.db.execute('SELECT COUNT(*) FROM attempt_hosts').fetchone() == (0,)


@pytest.mark.parametrize('fault', ['missing', 'host', 'environment'])
def test_local_gate_requires_the_original_host_and_environment(tmp_path, fault):
    with local_history.LocalRuntimeHistory(tmp_path) as store:
        run = store.begin('a' * 64, 1)
        node = complete(store, run)
        store.verify_run(run, {node: 'case'}, {'case': 'passed'})
        with store.db:
            if fault == 'missing':
                store.db.execute('DELETE FROM attempt_hosts')
            elif fault == 'host':
                store.db.execute("UPDATE attempt_hosts SET host='different-fixture-host'")
            else:
                store.db.execute("UPDATE attempt_hosts SET environment=?", ('f' * 64,))
        with pytest.raises(ValueError):
            store.verify_run(run, {node: 'case'}, {'case': 'passed'})


def test_failed_latest_attempt_keeps_its_host_without_using_an_older_duration(tmp_path):
    with local_history.LocalRuntimeHistory(tmp_path) as store:
        complete(store, store.begin('a' * 64, 1), seconds=3)
        complete(store, store.begin('b' * 64, 1), failure='call')
        assert store.snapshot(['case'])['tests'][0]['duration_ns'] is None
        assert store.db.execute('SELECT COUNT(*) FROM attempt_hosts').fetchone() == (2,)
        assert store.db.execute('SELECT COUNT(*) FROM phases').fetchone() == (6,)


def test_collect_only_does_not_capture_host_or_open_history(tmp_path):
    from support.catalog_project import make_catalog_project, check, effects
    root = make_catalog_project(tmp_path / 'repo')
    with (root / 'conftest.py').open('a') as stream:
        stream.write('''
from verification_support import local_history
def forbidden_capture():
    raise RuntimeError('collection must not capture the environment')
local_history.environment = forbidden_capture
''')
    code, report = check(root)
    assert code == 0 and report['catalog_valid'] and report['tests_run'] == 0
    assert not (root / LOCAL).exists() and effects(root) == []


def test_local_environment_metadata_does_not_relabel_explicit_pool_records(tmp_path):
    with RuntimeHistory(tmp_path) as store:
        run = store.begin('a' * 64, 1)
        store.start(run, 'node', 'identity', 'gw0', host='pool-fixture', environment='a' * 64)
    with local_history.LocalRuntimeHistory(tmp_path) as store:
        complete(store, store.begin('b' * 64, 1))
        assert store.db.execute('SELECT host,environment FROM attempt_hosts ORDER BY attempt LIMIT 1').fetchone() == (
            'pool-fixture', 'a' * 64)
