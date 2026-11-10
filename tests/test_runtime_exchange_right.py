"""A missing, unsafe or changed lane binding cannot create a successful gate."""
import json
import os

import pytest

from verification_support.runtime_history import RuntimeHistory, policy
from verification_support.ci_package_runtime import history_path
from test_runtime_exchange import configure
from test_runtime_history import complete


@pytest.mark.parametrize('fault', [
    'missing', 'json', 'object', 'bool-version', 'unknown-version', 'missing-exchange',
    'relative', 'source', 'ancestor', 'exchange-file', 'exchange-link',
    'config-link', 'config-parent-link', 'oversized', 'database-hardlink',
])
def test_invalid_exchange_fails_without_a_fallback_or_foreign_write(tmp_path, fault):
    root, exchange = tmp_path / 'repo', tmp_path / 'own-exchange'
    config = configure(root, exchange)
    original = tmp_path / 'preserved'
    original.write_bytes(b'preserve these original bytes')
    value = json.loads(config.read_text())
    if fault == 'missing':
        config.unlink()
    elif fault == 'json':
        config.write_text('{')
    elif fault == 'object':
        config.write_text('[]')
    elif fault in ('bool-version', 'unknown-version', 'missing-exchange', 'relative', 'source', 'ancestor', 'exchange-file'):
        if fault == 'bool-version':
            value['format_version'] = True
        elif fault == 'unknown-version':
            value['format_version'] = 99
        elif fault == 'missing-exchange':
            value.pop('exchange_directory')
        else:
            value['exchange_directory'] = {
                'relative': '../exchange', 'source': str(root / 'build'),
                'ancestor': str(tmp_path), 'exchange-file': str(original),
            }[fault]
        config.write_text(json.dumps(value))
    elif fault == 'exchange-link':
        exchange.rmdir()
        exchange.symlink_to(tmp_path, target_is_directory=True)
    elif fault == 'config-link':
        config.unlink()
        config.symlink_to(original)
    elif fault == 'config-parent-link':
        moved = root / 'original-config'
        config.parent.rename(moved)
        config.parent.symlink_to(moved, target_is_directory=True)
    elif fault == 'oversized':
        config.write_bytes(b' ' * 65537)
    elif fault == 'database-hardlink':
        os.link(original, exchange / 'specroad-test-runtime-history.sqlite3')
    with pytest.raises((OSError, ValueError)):
        RuntimeHistory(root)
    assert original.read_bytes() == b'preserve these original bytes'
    assert not (root / 'build/test-runtime-history.sqlite3').exists()
    assert not (tmp_path / 'exchange/specroad-test-runtime-history.sqlite3').exists()


def test_exchange_change_invalidates_gate_and_is_visible_to_selection_and_ci(tmp_path):
    root, one, two = tmp_path / 'repo', tmp_path / 'one', tmp_path / 'two'
    config = configure(root, one)
    two.mkdir()
    before = policy(root)
    with RuntimeHistory(root) as store:
        run = store.begin('a' * 64, 2)
        node = complete(store, run)
        store.verify_run(run, {node: 'case'}, {'case': 'passed'})
        value = json.loads(config.read_text())
        value['exchange_directory'] = str(two)
        config.write_text(json.dumps(value))
        assert policy(root) != before
        assert history_path(root) == two / 'specroad-test-runtime-history.sqlite3'
        with pytest.raises(ValueError):
            store.verify_run(run, {node: 'case'}, {'case': 'passed'})
        assert store.db.execute('SELECT COUNT(*) FROM phases').fetchone() == (3,)
    assert not history_path(root).exists()


def test_native_parallel_runner_records_only_its_own_exchange(tmp_path):
    from support.catalog_project import make_catalog_project, execute
    roots = [make_catalog_project(tmp_path / name) for name in ('first', 'second')]
    for index, root in enumerate(roots):
        configure(root, tmp_path / f'exchange-{index}')
    preserved = None
    for root in roots:
        result = execute(root, 'run_selected_tests.py', ['--workers', '2', '--expected-tests', '4',
            '--test-file', 'tests/test_subject.py', '--outdir', str(root / 'build/selected')])
        assert result.returncode == 0, (result.stdout + result.stderr).decode()
        with RuntimeHistory(root) as store:
            assert store.db.execute('SELECT COUNT(*) FROM attempts').fetchone() == (4,)
            assert store.db.execute('SELECT COUNT(*) FROM phases').fetchone() == (12,)
        if preserved is None:
            preserved = history_path(root).read_bytes()
    assert history_path(roots[0]).read_bytes() == preserved
    assert history_path(roots[0]) != history_path(roots[1])
