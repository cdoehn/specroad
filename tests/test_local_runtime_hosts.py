"""Local host labels are durable attempts, compatible with pool measurements."""
import platform

from dev.test_hosts.environment import environment, digest
from dev.test_hosts.history import estimates
from verification_support import local_history
from verification_support.runtime_history import RuntimeHistory
from test_runtime_history import complete


def test_local_attempts_capture_host_and_pool_compatible_environment_once(tmp_path, monkeypatch):
    expected = environment()
    calls = []
    def capture():
        calls.append(True)
        return expected
    monkeypatch.setattr(local_history.platform, 'node', lambda: 'fixture-host')
    monkeypatch.setattr(local_history, 'environment', capture)
    with local_history.LocalRuntimeHistory(tmp_path) as store:
        run = store.begin('a' * 64, 2)
        complete(store, run, 'one')
        complete(store, run, 'two', worker='gw1')
        assert store.db.execute('SELECT host,environment FROM attempt_hosts ORDER BY attempt').fetchall() == [
            ('fixture-host', digest(expected)), ('fixture-host', digest(expected))]
    assert calls == [True]


def test_old_unlabelled_and_other_host_measurements_remain_available(tmp_path, monkeypatch):
    with RuntimeHistory(tmp_path) as store:
        complete(store, store.begin('a' * 64, 1), seconds=9)
        original = store.db.execute('SELECT * FROM attempts').fetchall()
        original_phases = store.db.execute('SELECT * FROM phases ORDER BY attempt,phase').fetchall()
    for host, seconds in [('fixture-first', 1), ('fixture-second', 2)]:
        monkeypatch.setattr(local_history.platform, 'node', lambda: host)
        with local_history.LocalRuntimeHistory(tmp_path) as store:
            complete(store, store.begin('b' * 64, 1), seconds=seconds)
    with RuntimeHistory(tmp_path) as store:
        assert store.db.execute('SELECT * FROM attempts ORDER BY id LIMIT 1').fetchall() == original
        assert store.db.execute('SELECT * FROM phases WHERE attempt=? ORDER BY attempt,phase', (original[0][0],)).fetchall() == original_phases
        assert store.db.execute('SELECT h.host FROM attempts a LEFT JOIN attempt_hosts h ON h.attempt=a.id ORDER BY a.id').fetchall() == [
            (None,), ('fixture-first',), ('fixture-second',)]
        assert store.db.execute('SELECT COUNT(*) FROM phases').fetchone() == (9,)
    assert estimates(tmp_path, digest(environment())) == {
        'case\nfixture-first': 3.0, 'case\nfixture-second': 6.0}


def test_real_local_workers_record_host_before_setup_without_host_configuration(tmp_path):
    from support.catalog_project import make_catalog_project, execute
    expected = digest(environment())
    ids = [f'tests/test_subject.py::test_subject[{i}]' for i in range(2)]
    source = '''import platform, sqlite3
import pytest

@pytest.fixture(autouse=True)
def check_durable_start(request):
    with sqlite3.connect('file:build/test-runtime-history.sqlite3?mode=ro', uri=True) as db:
        row = db.execute('SELECT h.host,h.environment,a.complete FROM attempts a JOIN attempt_hosts h ON h.attempt=a.id WHERE a.node=?',
                         (request.node.nodeid,)).fetchone()
        assert row == (platform.node(), EXPECTED, 0)

@pytest.mark.parametrize('value', [0, 1])
def test_subject(value):
    assert value >= 0
'''.replace('EXPECTED', repr(expected))
    root = make_catalog_project(tmp_path / 'repo', ids=ids, source=source)
    result = execute(root, 'run_selected_tests.py', ['--outdir', str(root / 'build/selected'),
        '--workers', '2', '--expected-tests', '2', '--test-file', 'tests/test_subject.py'],
        environment={'SPECROAD_NESTED_TEST_RUN': '0'})
    assert result.returncode == 0, (result.stdout + result.stderr).decode()
    with RuntimeHistory(root) as store:
        assert store.db.execute('SELECT h.host,h.environment,COUNT(*) FROM attempt_hosts h GROUP BY h.host,h.environment').fetchall() == [
            (platform.node(), expected, 2)]
        assert store.db.execute('SELECT COUNT(*) FROM phases').fetchone() == (6,)
        assert all(row['duration_ns'] is not None for row in store.snapshot(ids)['tests'])
    assert not (root / 'build/selected/host-run.json').exists()
