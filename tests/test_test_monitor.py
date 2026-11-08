"""Machine contracts of the read-only multi-Apply monitor; no presentation tests."""
import json
import os
from pathlib import Path
import subprocess
import sys

from dev.status.monitor_data import filtered, history, run_tests, targets
from test_status_helpers import digest, lane
from verification_support.runtime_history import RuntimeHistory

ROOT = Path(__file__).resolve().parents[1]


def monitor_lane(workspace, suffix='', seconds=10):
    result = lane(workspace, suffix, seconds)
    dev = result[0]
    (dev / 'tools/test-monitor').write_bytes((ROOT / 'tools/test-monitor').read_bytes())
    return result


def invoke_monitor(dev, workspace, *args):
    result = subprocess.run([sys.executable, '-I', '-B', str(dev / 'tools/test-monitor'), '--once', '--json', *args],
        cwd=workspace, env={**os.environ, 'XDG_STATE_HOME': str(workspace / 'state'),
                           'XDG_CONFIG_HOME': str(workspace / 'config')},
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30, check=False)
    return result.returncode, json.loads(result.stdout)


def test_monitor_once_observes_each_lane_and_its_native_phase_durations(tmp_path):
    first, apply, one, lock = monitor_lane(tmp_path)
    second, apply2, two, lock2 = monitor_lane(tmp_path, '2', 20)
    before = [digest(p) for p in (one, two, lock, lock2)]
    code, value = invoke_monitor(first, tmp_path, '--all', '--match', 'MERGE')
    assert code == 0 and value['format_version'] == 1 and value['kind'] == 'specroad-test-monitor'
    assert [t['repository'] for t in value['repositories']] == [str(apply), str(apply2)]
    for target, seconds in zip(value['repositories'], (10, 20)):
        assert target['status']['data']['report']['status'] == 'completed'
        row = target['history']['data']['tests'][0]
        assert row['test_name'] == 'merge.slow' and row['completed'] and row['valid_measurement']
        assert [row[p + '_seconds'] for p in ('setup', 'call', 'teardown')] == [seconds] * 3
        assert row['total_seconds'] == 3 * seconds and row['elapsed_seconds'] is None
        assert target['status']['data']['run']['source'] == 'a' * 64
    assert [digest(p) for p in (one, two, lock, lock2)] == before


def test_monitor_default_is_repository_lane_and_explicit_targets_are_deduplicated(tmp_path):
    first, apply, one, lock = monitor_lane(tmp_path)
    second, apply2, two, lock2 = monitor_lane(tmp_path, '2', 20)
    code, value = invoke_monitor(second, tmp_path)
    assert code == 0 and [t['repository'] for t in value['repositories']] == [str(apply2)]
    code, value = invoke_monitor(first, tmp_path, '--apply-dir', str(apply2), '--apply-dir', str(apply), '--apply-dir', str(apply2))
    assert code == 0 and [t['repository'] for t in value['repositories']] == [str(apply2), str(apply)]


def test_monitor_partial_attempt_keeps_missing_phases_null_and_suppresses_old_success(tmp_path):
    dev, apply, database, lock = monitor_lane(tmp_path)
    with RuntimeHistory(tmp_path / 'storage', path=database) as store:
        run = store.begin('b' * 64, 1)
        node = 'tests/test_sample.py::merge.slow'
        store.start(run, node, 'merge.slow', 'gw0')
        store.observe(run, node, 'merge.slow', 'gw0', 'setup', 0.25, 'passed')
        expected = dict(zip([v[0] for v in store.db.execute('SELECT * FROM runs').description],
                            store.db.execute('SELECT * FROM runs WHERE id=?', (run,)).fetchone()))
    before = digest(database)
    rows, observed_run = run_tests(database, expected)
    assert observed_run['id'] == run and len(rows) == 1
    row = rows[0]
    assert row['setup_seconds'] == 0.25 and row['call_seconds'] is None and row['teardown_seconds'] is None
    assert row['total_seconds'] is None and row['elapsed_seconds'] >= 0
    assert row['phase'] == 'call' and row['completed'] is False and row['valid_measurement'] is False
    row = next(r for r in history(database) if r['test_name'] == 'merge.slow')
    assert row['total_seconds'] is None and row['status'] == 'unfinished' and row['elapsed_seconds'] is None
    assert digest(database) == before


def test_monitor_filters_full_population_before_limit_with_stable_phase_sorting():
    rows = [dict(test_name=name, nodeid='native::' + name, setup_seconds=setup, total_seconds=total)
            for name, setup, total in [('z', None, None), ('b', 4, 10), ('a', 4, 20), ('c', 9, 11)]]
    selected, count = filtered(rows, sort='setup', descending=True, limit=2)
    assert [r['test_name'] for r in selected] == ['c', 'a'] and count == 4
    selected, count = filtered(rows, sort='setup', descending=False, limit=0)
    assert [r['test_name'] for r in selected] == ['a', 'b', 'c', 'z']
    selected, count = filtered(rows, match='NATIVE::B', minimum=3, sort='setup', limit=1)
    assert [r['test_name'] for r in selected] == ['b'] and count == 1


def test_monitor_one_broken_target_does_not_hide_the_other_or_create_sources(tmp_path):
    dev, apply, database, lock = monitor_lane(tmp_path)
    missing = tmp_path / 'does-not-exist'
    before = digest(database)
    code, value = invoke_monitor(dev, tmp_path, '--apply-dir', str(missing), '--apply-dir', str(apply))
    assert code == 2
    bad, good = value['repositories']
    assert bad['status']['data']['report']['availability']['state'] == 'missing'
    assert bad['status']['stale'] and good['status']['data']['report']['status'] == 'completed'
    assert not missing.exists() and digest(database) == before


def test_monitor_cannot_assign_one_database_to_multiple_targets(tmp_path):
    dev, apply, database, lock = monitor_lane(tmp_path)
    code, value = invoke_monitor(dev, tmp_path, '--all', '--database', str(database))
    assert code == 2 and value['status'] == 'unavailable'


def test_monitor_discovers_additional_apply_lanes_without_registering_them(tmp_path):
    dev, apply, database, lock = monitor_lane(tmp_path)
    third = tmp_path / 'specroad-apply3'
    third.mkdir()
    assert targets(dev, all_targets=True) == [apply, tmp_path / 'specroad-apply2', third]
    assert not (third / '.patchharbor').exists()
