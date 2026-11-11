"""Selection, durable measurements and lossless evidence for diagnostic profiles."""
import json
import sqlite3

import pytest

from dev.profiling.artifacts import CHUNK_SIZE, capture, export
from dev.profiling.cli import parser, selectors, show_status
from dev.profiling.common import digest, relative_selector
from dev.profiling.runner import check_observation
from dev.profiling.selection import slowest
from dev.profiling.store import Store, reader


def project(tmp_path):
    (tmp_path / 'tests/sub').mkdir(parents=True)
    (tmp_path / 'tests/test_one.py').write_text('')
    (tmp_path / 'tests/sub/test_two.py').write_text('')
    return tmp_path


def prepared_store(root, pairs=None):
    store = Store(root / 'build/profiles.sqlite3', root, create=True)
    directory = root / 'build/run'
    directory.mkdir()
    store.create_run('run', root, directory, {})
    pairs = pairs or {'tests/test_one.py::test_one': 'test_one'}
    store.select('run', pairs, {}, 'a' * 64, digest(pairs), 1)
    return store, directory


def test_custom_file_directory_nodeid_union_and_filters_are_preserved(tmp_path):
    root = project(tmp_path)
    selection = root / 'chosen.json'
    selection.write_text(json.dumps(['tests/sub', 'tests/test_one.py::test_one[one]']))
    args = parser(root).parse_args(['run', '--selection', str(selection),
        '--test', 'tests/test_one.py::test_one[one]', '--test', 'tests/test_one.py',
        '-k', 'one or two', '-m', 'not slow'])
    assert selectors(root, args) == ['tests/test_one.py::test_one[one]', 'tests/test_one.py', 'tests/sub']
    assert (args.keyword, args.marker) == ('one or two', 'not slow')
    assert relative_selector(root, str(root / 'tests/test_one.py')) == 'tests/test_one.py'


@pytest.mark.parametrize('flags', [[], ['--all', '--slowest', '10'],
    ['--all', '--test', 'tests'], ['--slowest', '10', '--test', 'tests'],
    ['--test', '../outside.py'], ['--test', 'tools'], ['--all', '--history', 'history.sqlite3']])
def test_ambiguous_or_outside_selections_are_rejected_before_execution(tmp_path, flags):
    root = project(tmp_path)
    args = parser(root).parse_args(['run', *flags])
    with pytest.raises(ValueError):
        selectors(root, args)


@pytest.mark.parametrize('flag', ['-k', '-m'])
def test_expression_only_selection_uses_this_repository_tests(tmp_path, flag):
    root = project(tmp_path)
    assert selectors(root, parser(root).parse_args(['run', flag, 'some_test'])) == ['tests']


def test_selection_file_rejects_empty_and_option_injection(tmp_path):
    root = project(tmp_path)
    selection = root / 'chosen.json'
    for content in ([], ['--collect-only'], {'tests': ['tests']}, [17]):
        selection.write_text(json.dumps(content))
        with pytest.raises(ValueError):
            selectors(root, parser(root).parse_args(['run', '--selection', str(selection)]))


def test_latest_failed_or_incomplete_measurements_do_not_resurrect_older_success(tmp_path):
    from verification_support.runtime_history import RuntimeHistory
    from test_runtime_history import complete
    pairs = {name: name for name in ('valid-a', 'valid-b', 'broken', 'new')}
    with RuntimeHistory(tmp_path) as history:
        for name, seconds in (('valid-a', 3), ('valid-b', 3), ('retired', 100), ('broken', 90)):
            complete(history, history.begin('a' * 64, 1), name, seconds=seconds)
        history.start(history.begin('b' * 64, 1), 'tests/test_sample.py::broken', 'broken', 'gw0')
        path = history.path
    before = path.read_bytes()
    selected, provenance = slowest(pairs, path, 10)
    assert list(selected) == ['valid-a', 'valid-b']
    assert all(row['duration_ns'] == 9_000_000_000 for row in provenance.values())
    assert path.read_bytes() == before
    assert list(slowest(pairs, path, 1)[0]) == ['valid-a']


def test_profile_database_never_initializes_a_runtime_history_database(tmp_path):
    path = tmp_path / 'runtime.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript('CREATE TABLE metadata(id INTEGER, version INTEGER); INSERT INTO metadata VALUES(1,1);')
    before = path.read_bytes()
    with pytest.raises((ValueError, sqlite3.Error)):
        Store(path, tmp_path / 'repository', create=True)
    assert path.read_bytes() == before


def test_phase_calls_and_callers_survive_reopening_and_no_attempt_is_repeated(tmp_path):
    store, directory = prepared_store(tmp_path)
    node = 'tests/test_one.py::test_one'
    before = dict(pid=123, tid=124, time_ns=100, monotonic_ns=10)
    after = dict(pid=123, tid=124, time_ns=200, monotonic_ns=110)
    stats = {(str(tmp_path / 'src/a.py'), 10, 'parse'): (2, 3, .2, .4, {('~', 0, 'caller'): (2, 3, .1, .3)})}
    with store:
        store.begin_test('run', node, 'gw0', 123, 124, 0, 100)
        with pytest.raises(ValueError):
            store.begin_test('run', node, 'gw0', 123, 124, 0, 101)
        for name in ('setup', 'call', 'teardown'):
            store.phase('run', node, name, before, after, stats, tmp_path)
            store.phase_outcome('run', node, name, 'passed')
        store.end_test('run', node, 200)
        assert store.finish('run', 'passed', 0, outcomes={'test_one': 'passed'}) == 'passed'
    value = show_status(store.path, 'run')
    assert value['tests'][0]['status'] == 'passed'
    with reader(store.path) as db:
        assert db.execute('SELECT SUM(elapsed_ns) FROM phases').fetchone()[0] == 300
        assert tuple(db.execute('SELECT filename,line,name,calls FROM python_functions LIMIT 1').fetchone()) == ('src/a.py', 10, 'parse', 3)
        assert db.execute('SELECT COUNT(*) FROM python_callers').fetchone()[0] == 3


def test_exit_zero_without_complete_profile_phases_is_not_success(tmp_path):
    store, _ = prepared_store(tmp_path)
    with store:
        assert store.finish('run', 'passed', 0, outcomes={'test_one': 'passed'}) == 'incomplete'
    assert show_status(store.path, 'run')['tests'][0]['status'] == 'incomplete'


def test_raw_artifact_is_lossless_in_database_without_original_file(tmp_path):
    store, directory = prepared_store(tmp_path)
    raw = bytes(range(256)) * (CHUNK_SIZE // 128 + 7)
    path = directory / 'strace.123'
    path.write_bytes(raw)
    with store:
        identifier = capture(store, 'run', directory, path, kind='strace', pid=123)
        assert capture(store, 'run', directory, path, kind='strace', pid=123) == identifier
        assert store.db.execute('SELECT COUNT(*) FROM artifact_chunks').fetchone()[0] == 3
    path.unlink()
    output = directory / 'exported.trace'
    with reader(store.path) as db:
        export(db, identifier, output)
        assert output.read_bytes() == raw
        with pytest.raises(FileExistsError):
            export(db, identifier, output)


def test_corrupt_export_does_not_publish_partial_output(tmp_path):
    store, directory = prepared_store(tmp_path)
    path = directory / 'profile.pstats'
    path.write_bytes(b'profile evidence')
    with store:
        identifier = capture(store, 'run', directory, path, kind='cprofile')
        with store.db:
            store.db.execute('UPDATE artifacts SET sha256=? WHERE id=?', ('0' * 64, identifier))
    output = directory / 'bad-export'
    with reader(store.path) as db, pytest.raises(ValueError):
        export(db, identifier, output)
    assert not output.exists()
    assert not list(directory.glob('.profile-export-*'))


@pytest.mark.parametrize('fault', ['internal_error', 'missing', 'skip', 'false_success', 'malformed'])
def test_native_observation_cannot_hide_failure_with_exit_zero(fault):
    pairs = {'tests/test_sample.py::test_one': 'one'}
    observation = dict(pytest_exit_code=0, suite_passed=True, errors=[],
                       nodeid_to_test_id=pairs, tests_run=1, test_outcomes={'one': 'passed'})
    if fault == 'internal_error':
        observation['errors'] = ['pytest_internal_error']
    elif fault == 'missing':
        observation['nodeid_to_test_id'] = {}
    elif fault == 'skip':
        observation['test_outcomes'] = {'one': 'skipped'}
    elif fault == 'false_success':
        observation['suite_passed'] = False
    else:
        observation = []
    with pytest.raises(ValueError):
        check_observation(observation, pairs, 0, None)
