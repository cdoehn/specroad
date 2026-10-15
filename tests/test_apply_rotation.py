"""Commit rotation, persistent numbering and exact parallel execution contracts."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from verification_support import apply_rotation as rotation
from verification_support.process_environment import test_environment as controlled_environment

ANCHOR = "a" * 40
NEXT = "b" * 40
PAIRS = {f"tests/test_sample.py::test_{n}": f"case.{n}" for n in range(6)}


def registry(ids=None):
    return {"format_version": 1, "anchor_commit": ANCHOR,
            "test_ids": sorted(PAIRS.values()) if ids is None else ids}


def test_first_commit_even_second_odd_then_even():
    value = registry()
    parts = [rotation.select_partition(PAIRS, value, n, value if n else None) for n in range(3)]
    assert set(parts[0].values()) == {"case.0", "case.2", "case.4"}
    assert set(parts[1].values()) == {"case.1", "case.3", "case.5"}
    assert parts[2] == parts[0]
    assert not parts[0].keys() & parts[1].keys()
    assert parts[0] | parts[1] == PAIRS


def test_new_ids_append_and_retired_numbers_remain_reserved():
    previous = registry()
    current = {n: i for n, i in PAIRS.items() if i != "case.2"}
    current["tests/test_new.py::test_new"] = "case.-1"
    numbers = rotation.validate_registry(registry(previous["test_ids"] + ["case.-1"]),
                                         current.values(), previous)
    assert numbers["case.2"] == 2 and numbers["case.-1"] == 6
    assert all(numbers[i] == n for n, i in enumerate(previous["test_ids"]))


@pytest.mark.parametrize("change", ["reorder", "remove", "duplicate", "anchor", "missing", "extra"])
def test_renumbering_or_unbound_registry_is_rejected(change):
    previous = registry(); current = deepcopy(previous)
    if change == "reorder": current["test_ids"].reverse()
    elif change == "remove": current["test_ids"].pop(0)
    elif change == "duplicate": current["test_ids"].append("case.0")
    elif change == "anchor": current["anchor_commit"] = NEXT
    elif change == "missing": current["test_ids"] = current["test_ids"][:-1]
    else: current["test_ids"].append("uncollected.new.id")
    with pytest.raises(ValueError):
        rotation.select_partition(PAIRS, current, 1, previous)


def git_reader(root, history, existing=None):
    def run(command, **kwargs):
        args = command[2:]
        if args == ["rev-parse", "--show-toplevel"]: text = str(root)
        elif args == ["rev-list", "--first-parent", "HEAD"]: text = "\n".join(history)
        elif args == ["ls-tree", "--name-only", "HEAD", "--", rotation.REGISTRY]:
            text = rotation.REGISTRY if existing else ""
        elif args == ["show", history[0] + ":" + rotation.REGISTRY]: text = json.dumps(existing)
        else: raise AssertionError(args)
        return SimpleNamespace(returncode=0, stdout=(text + "\n").encode())
    return run


def test_only_commits_advance_rotation_and_retry_keeps_parity(tmp_path):
    value = registry()
    before = git_reader(tmp_path, [ANCHOR])
    assert rotation.commit_context(tmp_path, value, runner=before) == (ANCHOR, 0, None)
    assert rotation.commit_context(tmp_path, value, runner=before) == (ANCHOR, 0, None)
    after = git_reader(tmp_path, [NEXT, ANCHOR], value)
    assert rotation.commit_context(tmp_path, value, runner=after) == (NEXT, 1, value)


def test_anchor_reset_cannot_restart_initial_numbering(tmp_path):
    changed = dict(registry(), anchor_commit=NEXT)
    _, sequence, previous = rotation.commit_context(tmp_path, changed,
        runner=git_reader(tmp_path, [NEXT, ANCHOR], registry()))
    with pytest.raises(ValueError): rotation.select_partition(PAIRS, changed, sequence, previous)


def test_missing_anchor_or_lost_committed_registry_fails(tmp_path):
    for history in ([NEXT], [NEXT, ANCHOR]):
        with pytest.raises(ValueError):
            rotation.commit_context(tmp_path, registry(), runner=git_reader(tmp_path, history))


@pytest.mark.parametrize("workers", [0, 1, -1, True, "4"])
def test_nonparallel_workers_are_rejected(tmp_path, workers):
    with pytest.raises(ValueError): rotation.parallel_command(tmp_path, tmp_path, 3, workers)


@pytest.mark.parametrize("bad", [{}, {"tests/a.py::x": "case.0", "tests/a.py::y": "case.0"},
                                {"--sr-gate": "case.0"}, {"tests/a.py::x\n--sr-gate": "case.0"}])
def test_invalid_selection_cannot_become_a_gate(bad):
    with pytest.raises(ValueError): rotation.select_partition(bad, registry(), 0)


@pytest.mark.parametrize("parity,failing", [(0, False), (1, False), (1, True)])
def test_real_parallel_argument_file_runs_only_selected_tests(tmp_path, parity, failing):
    root = Path(__file__).resolve().parents[1]
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    lines = [f"def test_{n}():\n    assert {not (failing and n == 1)}\n" for n in range(4)]
    (tmp_path / "test_sample.py").write_text("\n".join(lines))
    selected = [f"test_sample.py::test_{n}" for n in range(4) if n % 2 == parity]
    (tmp_path / "nodeids.txt").write_text("\n".join(selected) + "\n")
    command = rotation.parallel_command(root, tmp_path, 2, 2)
    command[-1:-1] = ["-c", str(tmp_path / "pytest.ini"), "--confcutdir", str(tmp_path),
                     "-p", "verification_support.pytest_backend"]
    result = subprocess.run(command, cwd=tmp_path, env=controlled_environment(os.environ),
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    observed = json.loads((tmp_path / "observations.json").read_text())
    assert result.returncode == (1 if failing else 0)
    assert set(observed["nodeids"]) == set(selected)
    assert observed["tests_run"] == 2
    assert observed["suite_passed"] is (not failing)
    assert all(name.startswith("gw") for name in observed["worker_test_counts"])


@pytest.mark.parametrize("fault", [None, "skip", "wrong_ids", "process", "source", "head", "missing"])
def test_apply_gate_checks_exact_observed_partition_and_retains_failure(tmp_path, monkeypatch, fault):
    root = tmp_path / "repo"; (root / "verification").mkdir(parents=True)
    (root / rotation.REGISTRY).write_text(json.dumps(registry()))
    catalog = {"source_sha256": "bound", "collected_tests": len(PAIRS), "nodeid_to_test_id": PAIRS}
    monkeypatch.setattr(rotation, "run_catalog_preflight",
        lambda root, path: path.write_text(json.dumps(catalog)) or True)
    monkeypatch.setattr(rotation, "commit_context", lambda *a: (ANCHOR, 0, None))
    monkeypatch.setattr(rotation, "source_identity", lambda root: "bound")
    outdir = tmp_path / "reports"; calls = []
    def execute(command, **kwargs):
        calls.append(command)
        selected = {n: i for n, i in PAIRS.items() if i in {"case.0", "case.2", "case.4"}}
        if fault == "wrong_ids": selected = {n: i for n, i in PAIRS.items() if i in {"case.1", "case.3", "case.5"}}
        observed = {"observation_format_version": 1, "engine": "pytest", "nodeids": list(selected),
            "nodeid_to_test_id": selected, "test_outcomes": {i: "passed" for i in selected.values()},
            "suite_passed": True, "errors": [], "tests_run": 3, "pytest_exit_code": 0,
            "worker_test_counts": {"gw0": 2, "gw1": 1}}
        if fault == "skip": observed["test_outcomes"]["case.0"] = "skipped"
        if fault == "source": monkeypatch.setattr(rotation, "source_identity", lambda root: "changed")
        if fault == "head": monkeypatch.setattr(rotation, "commit_context", lambda *a: (NEXT, 1, registry()))
        if fault != "missing": (outdir / "observations.json").write_text(json.dumps(observed))
        return SimpleNamespace(returncode=1 if fault == "process" else 0)
    result = rotation.run_apply_partition(root, outdir, runner=execute)
    assert len(calls) == 1
    assert result["selected_passed"] is (fault is None)
    assert result["full_suite_passed"] is None
    assert result["commit_sequence"] == 0 and result["parity"] == "even"
    assert result["expected_tests"] == 3 and result["collected_tests"] == 6
    assert json.loads((root / rotation.REGISTRY).read_text()) == registry()


def test_failed_catalog_prevents_any_test_execution(tmp_path, monkeypatch):
    monkeypatch.setattr(rotation, "run_catalog_preflight", lambda *a: False)
    with pytest.raises(ValueError):
        rotation.run_apply_partition(tmp_path, tmp_path / "build/run",
            runner=lambda *a, **k: pytest.fail("tests must not start"))
