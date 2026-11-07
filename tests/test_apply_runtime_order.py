"""Runtime ordering preserves the exact Apply population and frozen evidence."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from verification_support import apply_rotation as rotation, apply_gate
from verification_support.bundle_contract import canonical
from verification_support.runtime_history import RuntimeHistory
from verification_support.worker_order import latest_runtime_order
from test_apply_commit_plan import setup_gate, make_plan
from test_apply_rotation import NEXT
from test_runtime_history import complete


def inputs(durations):
    selected = {f'tests/test_sample.py::case.{i:03d}': f'case.{i:03d}'
                for i in range(len(durations))}
    snapshot = {'format_version': 1, 'kind': 'specroad-latest-runtime-snapshot-v1',
                'tests': [{'test_id': identity, 'duration_ns': duration}
                          for identity, duration in zip(selected.values(), durations)]}
    return selected, snapshot


def test_long_tests_start_in_every_initial_queue_instead_of_one_slow_queue():
    selected, snapshot = inputs([1_000_000_000_000] * 8 + [1_000_000_000] * 24)
    before = deepcopy((selected, snapshot))
    ordered = latest_runtime_order(selected, snapshot, 4)
    assert len(ordered) == len(set(ordered)) == 32 and set(ordered) == set(selected)
    durations = {node: row['duration_ns'] for node, row in zip(selected, snapshot['tests'])}
    # For 32 tests and four workers xdist initially takes eight tests per queue.
    # The original lexical order has all eight long tests in its first queue.
    assert sum(durations[n] for n in list(selected)[:8]) == 8_000_000_000_000
    for start in (0, 8, 16, 24):
        queue = ordered[start:start + 8]
        assert [durations[n] for n in queue[:2]] == [1_000_000_000_000] * 2
        assert sum(durations[n] for n in queue) == 2_006_000_000_000
    assert (selected, snapshot) == before


@pytest.mark.parametrize('workers', [1, 2, 3, 10])
def test_ties_unknown_and_zero_durations_keep_all_tests_deterministically(workers):
    selected, snapshot = inputs([None, 0, 300_000_000_000, None, 1])
    before = deepcopy(snapshot)
    ordered = latest_runtime_order(selected, snapshot, workers)
    reversed_selection = dict(reversed(list(selected.items())))
    assert ordered == latest_runtime_order(reversed_selection, snapshot, workers)
    assert set(ordered) == set(selected) and len(ordered) == len(set(ordered))
    assert snapshot == before  # Estimates must never become persisted measurements.
    if workers == 1:
        assert ordered == [list(selected)[i] for i in (0, 2, 3, 1, 4)]


@pytest.mark.parametrize('failure', ['call', 'interrupted'])
def test_latest_failed_or_interrupted_attempt_is_unknown_for_ordering(tmp_path, failure):
    with RuntimeHistory(tmp_path) as history:
        complete(history, history.begin('a' * 64, 4), 'fast', seconds=1)
        complete(history, history.begin('a' * 64, 4), 'slow', seconds=200)
        if failure == 'call':
            complete(history, history.begin('b' * 64, 4), 'fast', failure='call')
        else:
            history.start(history.begin('b' * 64, 4), 'tests/test_sample.py::fast', 'fast', 'gw0')
        selected = {'tests/test_sample.py::fast': 'fast',
                    'tests/test_sample.py::slow': 'slow', 'tests/test_sample.py::new': 'new'}
        snapshot = history.snapshot(selected.values())
        assert {row['test_id']: row['duration_ns'] for row in snapshot['tests']} == {
            'fast': None, 'slow': 600_000_000_000, 'new': None}
        assert latest_runtime_order(selected, snapshot, 1) == [
            'tests/test_sample.py::slow', 'tests/test_sample.py::fast', 'tests/test_sample.py::new']
        assert history.snapshot(selected.values()) == snapshot


def test_runner_orders_required_union_using_frozen_snapshot_then_independent_gate(tmp_path, monkeypatch):
    root, pairs, _, path = setup_gate(tmp_path, monkeypatch)
    plan = make_plan(sorted(pairs.values()))
    path.write_bytes(canonical(plan))
    out = tmp_path / 'gate'
    frozen = {}

    def execute(command, **kwargs):
        nodes = (out / 'nodeids.txt').read_text().splitlines()
        assert len(nodes) == len(set(nodes)) == len(pairs) and set(nodes) == set(pairs)
        assert command[command.index('--dist') + 1] == 'worksteal'
        assert command[command.index('-n') + 1] == '4'
        assert command[-1] == '@' + str(out / 'nodeids.txt')
        # Twelve known durations 0,3,...,33 seconds: each initial queue of three
        # starts a different long test. The two slowest remain required.
        assert [pairs[nodes[i]] for i in (0, 3, 6, 9)] == ['case.11', 'case.10', 'case.9', 'case.8']
        frozen['raw'] = (out / 'runtime-snapshot.json').read_bytes()
        with RuntimeHistory(root) as history:
            complete(history, history.begin('b' * 64, 4), 'case.11', failure='call')
        observed = {node: pairs[node] for node in nodes}
        (out / 'observations.json').write_text(json.dumps(dict(
            observation_format_version=1, engine='pytest', nodeids=nodes,
            nodeid_to_test_id=observed, test_outcomes={i: 'passed' for i in observed.values()},
            suite_passed=True, errors=[], tests_run=len(observed), pytest_exit_code=0,
            worker_test_counts={f'gw{i}': 3 for i in range(4)})))
        return SimpleNamespace(returncode=0)

    result = rotation.run_apply_partition(root, out, workers=4,
        test_plan=path, commit_id='step.W', runner=execute)
    assert result['selected_passed'] and result['nodeid_to_test_id'] == pairs
    assert set(result['required_tests']['restored_slow_test_ids']) == {'case.10', 'case.11'}
    assert (out / 'runtime-snapshot.json').read_bytes() == frozen['raw']
    proof = apply_gate.verify_commit_gate(root, out, source='a' * 64, head=NEXT, test_plan=plan)
    assert proof['tests'] == proof['required_tests'] == 12


@pytest.mark.parametrize('fault', ['omit', 'duplicate', 'substitute'])
def test_reordered_observations_cannot_hide_population_errors(tmp_path, monkeypatch, fault):
    root, pairs, plan, path = setup_gate(tmp_path, monkeypatch)
    out = tmp_path / 'gate'

    def execute(command, **kwargs):
        nodes = (out / 'nodeids.txt').read_text().splitlines()
        if fault == 'omit': nodes.pop()
        elif fault == 'duplicate': nodes[-1] = nodes[0]
        else: nodes[-1] = next(node for node in pairs if node not in nodes)
        observed = {node: pairs[node] for node in nodes}
        (out / 'observations.json').write_text(json.dumps(dict(
            observation_format_version=1, engine='pytest', nodeids=nodes,
            nodeid_to_test_id=observed, test_outcomes={i: 'passed' for i in observed.values()},
            suite_passed=True, errors=[], tests_run=len(nodes), pytest_exit_code=0,
            worker_test_counts={'gw0': len(nodes), 'gw1': 0})))
        return SimpleNamespace(returncode=0)

    result = rotation.run_apply_partition(root, out, workers=4,
        test_plan=path, commit_id='step.W', runner=execute)
    assert not result['selected_passed']
    with pytest.raises(ValueError):
        apply_gate.verify_commit_gate(root, out, source='a' * 64, head=NEXT, test_plan=plan)
