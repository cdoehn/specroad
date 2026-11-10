"""Separate native runtime stores for independently configured Apply lanes."""
import json

import pytest

from verification_support.runtime_history import RuntimeHistory, POLICY, LOCAL, SHARED, EXCHANGE, policy
from verification_support.ci_package_runtime import history_path
from test_runtime_history import complete


def configure(root, exchange):
    (root / 'verification').mkdir(parents=True, exist_ok=True)
    (root / POLICY).write_text(json.dumps(dict(format_version=1,
        selection='latest_valid_fifth', database=EXCHANGE)))
    (root / '.patchharbor').mkdir(exist_ok=True)
    # Synthetic local registration marker; no global registry or host API.
    (root / '.patchharbor/id').write_text('00000000-0000-0000-0000-000000000001\n')
    exchange.mkdir(parents=True, exist_ok=True)
    (root / '.patchharbor/config.json').write_text(json.dumps(dict(
        format_version=1, exchange_directory=str(exchange))))
    return root / '.patchharbor/config.json'


def test_independent_exchanges_keep_same_test_identity_and_failures_separate(tmp_path):
    first, second = tmp_path / 'first', tmp_path / 'second'
    one, two = tmp_path / 'exchange-one', tmp_path / 'exchange-two'
    configure(first, one)
    configure(second, two)
    with RuntimeHistory(first) as store:
        run = store.begin('a' * 64, 2)
        complete(store, run, seconds=2)
        store.finish(run, 0)
    original = history_path(first).read_bytes()
    with RuntimeHistory(second) as store:
        run = store.begin('b' * 64, 2)
        complete(store, run, seconds=100, failure='call')
        store.finish(run, 1)
        assert store.snapshot(['case'])['tests'][0]['duration_ns'] is None
        assert store.db.execute('SELECT COUNT(*) FROM attempts').fetchone() == (1,)
    assert history_path(first).read_bytes() == original
    assert history_path(first) == one / 'specroad-test-runtime-history.sqlite3'
    assert history_path(second) == two / 'specroad-test-runtime-history.sqlite3'
    with RuntimeHistory(first) as store:
        assert store.snapshot(['case'])['tests'][0]['duration_ns'] == 6_000_000_000
        assert store.db.execute('SELECT COUNT(*) FROM phases').fetchone() == (3,)


def test_reopening_configured_exchange_preserves_older_attempts(tmp_path):
    root, exchange = tmp_path / 'repo', tmp_path / 'own-exchange'
    configure(root, exchange)
    for seconds in (3, 1):
        with RuntimeHistory(root) as store:
            run = store.begin('a' * 64, 2)
            complete(store, run, seconds=seconds)
            store.finish(run, 0)
    with RuntimeHistory(root) as store:
        assert store.snapshot(['case'])['tests'][0]['duration_ns'] == 3_000_000_000
        assert store.db.execute('SELECT COUNT(*) FROM attempts').fetchone() == (2,)
        assert store.db.execute('SELECT COUNT(*) FROM phases').fetchone() == (6,)


def test_unregistered_copies_without_config_use_separate_build_histories(tmp_path):
    for name in ('first', 'second'):
        root = tmp_path / name
        (root / 'verification').mkdir(parents=True)
        (root / POLICY).write_text(json.dumps(dict(format_version=1,
            selection='latest_valid_fifth', database=EXCHANGE)))
        with RuntimeHistory(root) as store:
            assert store.path == root / LOCAL
            assert store.db.execute('SELECT COUNT(*) FROM attempts').fetchone() == (0,)
            complete(store, store.begin('a' * 64, 2))
        assert history_path(root) == root / LOCAL
    assert not (tmp_path / 'exchange').exists()


@pytest.mark.parametrize('database', [LOCAL, SHARED], ids=['local', 'legacy-shared'])
def test_existing_runtime_policies_keep_their_original_destination(tmp_path, database):
    root = tmp_path / 'repo'
    (root / 'verification').mkdir(parents=True)
    value = dict(format_version=1, selection='latest_valid_fifth', database=database)
    (root / POLICY).write_text(json.dumps(value))
    assert policy(root) == value
    with RuntimeHistory(root) as store:
        assert store.path == (root / database).resolve()
    assert not (root / '.patchharbor').exists()
