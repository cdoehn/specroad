"""Latest attempts, preserved history and actual automatic parallel recording."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from verification_support.runtime_history import RuntimeHistory, filter_latest, LOCAL, POLICY
from verification_support.runtime_baseline import BASELINE, make_baseline, encoded
from test_runtime_baseline import measurement


def complete(store, run, identity='case', seconds=1, worker='gw0', *, failure=None):
    node = 'tests/test_sample.py::' + identity
    store.start(run, node, identity, worker)
    for phase in ('setup', 'call', 'teardown'):
        store.observe(run, node, identity, worker, phase, seconds,
                      'failed' if phase == failure else 'passed')
    return node


def test_first_run_persists_all_phases_without_calibration_request(tmp_path):
    with RuntimeHistory(tmp_path) as store:
        run = store.begin('a'*64, 4)
        complete(store, run)
    with RuntimeHistory(tmp_path) as reopened:
        assert reopened.snapshot(['case'])['tests'][0]['duration_ns'] == 3_000_000_000
        assert reopened.db.execute('SELECT COUNT(*) FROM phases').fetchone() == (3,)


def test_latest_success_replaces_duration_but_retains_each_attempt(tmp_path):
    with RuntimeHistory(tmp_path) as store:
        for seconds in (10, 2):
            run = store.begin('a'*64, 4)
            complete(store, run, seconds=seconds)
        assert store.snapshot(['case'])['tests'][0]['duration_ns'] == 6_000_000_000
        assert store.db.execute('SELECT COUNT(*) FROM attempts').fetchone() == (2,)
        assert store.db.execute('SELECT COUNT(*) FROM phases').fetchone() == (6,)


@pytest.mark.parametrize('failure', ['setup', 'call', 'teardown'])
def test_failed_latest_attempt_never_falls_back_and_successful_retry_restores(tmp_path, failure):
    with RuntimeHistory(tmp_path) as store:
        complete(store, store.begin('a'*64, 4), seconds=100)
        complete(store, store.begin('b'*64, 4), failure=failure)
        assert store.snapshot(['case'])['tests'][0]['duration_ns'] is None
        complete(store, store.begin('c'*64, 4), seconds=2)
        assert store.snapshot(['case'])['tests'][0]['duration_ns'] == 6_000_000_000


def test_start_immediately_invalidates_even_before_first_phase(tmp_path):
    with RuntimeHistory(tmp_path) as store:
        complete(store, store.begin('a'*64, 4))
        run = store.begin('a'*64, 4)
        store.start(run, 'tests/test_sample.py::case', 'case', 'gw1')
    with RuntimeHistory(tmp_path) as store:
        assert store.snapshot(['case'])['tests'][0]['duration_ns'] is None


def test_late_completion_of_older_attempt_cannot_replace_newer_start(tmp_path):
    with RuntimeHistory(tmp_path) as first, RuntimeHistory(tmp_path) as second:
        older = first.begin('a'*64, 4)
        first.start(older, 'tests/test_sample.py::case', 'case', 'gw0')
        complete(second, second.begin('b'*64, 4), seconds=2)
        for phase in ('setup', 'call', 'teardown'):
            first.observe(older, 'tests/test_sample.py::case', 'case', 'gw0', phase, 99, 'passed')
        assert first.snapshot(['case'])['tests'][0]['duration_ns'] == 6_000_000_000


def test_seeds_are_idempotent_and_never_override_failed_newer_attempt(tmp_path):
    (tmp_path/'verification').mkdir()
    (tmp_path/BASELINE).write_bytes(encoded(make_baseline(measurement())))
    with RuntimeHistory(tmp_path) as store:
        store.seed(tmp_path)
        store.seed(tmp_path)
        assert store.db.execute('SELECT COUNT(*) FROM seeds').fetchone() == (10,)
        run = store.begin('a'*64, 4)
        complete(store, run, 'case.9', failure='call')
        store.seed(tmp_path)
        rows = store.snapshot(['case.9', 'new'])['tests']
        assert all(r['duration_ns'] is None for r in rows)
        assert store.db.execute('SELECT COUNT(*) FROM seeds').fetchone() == (10,)


def test_latest_filter_uses_current_valid_population_ties_and_retired_ids(tmp_path):
    with RuntimeHistory(tmp_path) as store:
        for i in range(10):
            complete(store, store.begin('a'*64, 4), f'case.{i}', seconds=1)
        complete(store, store.begin('a'*64, 4), 'case.9', failure='call')
        pairs = {f'node{i}': f'case.{i}' for i in range(9)} | {'new': 'new'}
        snapshot = store.snapshot(pairs.values())
        kept, receipt = filter_latest(pairs, snapshot)
        assert receipt['measured_tests'] == 9
        assert receipt['excluded_test_ids'] == ['case.0']
        assert len(kept) == 9 and kept['new'] == 'new'


def test_apply_freezes_latest_snapshot_and_does_not_filter_other_groups(tmp_path, monkeypatch):
    from verification_support import apply_rotation as rotation
    from test_apply_thirds import thirds
    from test_apply_rotation import NEXT
    root = tmp_path/'repo'; (root/'verification').mkdir(parents=True)
    (root/POLICY).write_text(json.dumps(dict(format_version=1, selection='latest_valid_fifth', database=LOCAL)))
    pairs = {f'tests/test_sample.py::case.{i}': f'case.{i}' for i in range(12)}
    registry = thirds(sorted(pairs.values()))
    (root/rotation.REGISTRY).write_text(json.dumps(registry))
    with RuntimeHistory(root) as store:
        for i in range(12):
            complete(store, store.begin('a'*64, 4), f'case.{i}', seconds=i)
    monkeypatch.setattr(rotation, 'run_catalog_preflight', lambda r,p: p.write_text(json.dumps(
        dict(source_sha256='bound', collected_tests=12, nodeid_to_test_id=pairs))) or True)
    monkeypatch.setattr(rotation, 'commit_context', lambda *a: (NEXT, 2, registry))
    monkeypatch.setattr(rotation, 'source_identity', lambda *a: 'bound')
    out = tmp_path/'reports'
    def execute(command, **kwargs):
        nodes = (out/'nodeids.txt').read_text().splitlines()
        selected = {n:pairs[n] for n in nodes}
        assert set(selected.values()) == {'case.3', 'case.6', 'case.9'}
        with RuntimeHistory(root) as store:
            complete(store, store.begin('b'*64, 4), 'case.1', seconds=999)
        observation = dict(observation_format_version=1, engine='pytest', nodeids=nodes,
            nodeid_to_test_id=selected, test_outcomes={i:'passed' for i in selected.values()},
            suite_passed=True, errors=[], tests_run=len(nodes), pytest_exit_code=0,
            worker_test_counts={'gw0':len(nodes), 'gw1':0})
        (out/'observations.json').write_text(json.dumps(observation))
        return SimpleNamespace(returncode=0)
    result = rotation.run_apply_partition(root, out, runner=execute)
    assert result['selected_passed'] and result['selection_binding']['format_version'] == 3
    assert result['runtime_filter']['excluded_test_ids'] == ['case.10', 'case.11']
    assert result['test_scope'] == 'stable_modulo_partition_with_latest_runtime_filter'


def test_real_parallel_dev_runs_automatically_record_and_repeat_all_selected_tests(tmp_path):
    from support.catalog_project import make_catalog_project, execute, NATIVE_IDS, LEGACY_ID
    root = make_catalog_project(tmp_path)
    for attempt in range(2):
        result = execute(root, 'run_selected_tests.py', ['--outdir', str(root/f'build/selected{attempt}'),
            '--workers','2','--expected-tests','4','--test-file','tests/test_subject.py'])
        assert result.returncode == 0, (result.stdout+result.stderr).decode()
    with RuntimeHistory(root) as store:
        assert store.db.execute('SELECT COUNT(*) FROM attempts').fetchone() == (8,)
        rows = store.snapshot([*NATIVE_IDS, LEGACY_ID])['tests']
        assert all(r['duration_ns'] is not None for r in rows)
