"""Frozen test runtimes filter automatic Apply, never explicit or complete runs."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from verification_support.runtime_baseline import (
    BASELINE, RuntimeMeasurements, encoded, filter_partition, freeze, load_baseline,
    make_baseline, validate_baseline,
)


def measurement(count=10):
    return {"format_version": 1, "kind": "specroad-full-test-runtimes-v1",
            "source_sha256": "a" * 64, "measured_at": "2026-10-28T10:00:00+00:00",
            "workers": 4, "full_suite_passed": True,
            "tests": [{"test_id": "case." + str(i),
                       "nodeid": "tests/test_sample.py::test_" + str(i),
                       "phase_ns": {"setup": i, "call": 10 * i, "teardown": i}}
                      for i in range(count)]}


def test_slowest_fifth_is_frozen_by_total_phase_time_and_identity_tie_break():
    value = measurement()
    value["tests"][0]["phase_ns"]["setup"] = 9999
    value["tests"][1]["phase_ns"]["teardown"] = 9999
    baseline = make_baseline(value)
    assert baseline["excluded_test_ids"] == ["case.0", "case.1"]
    for row in value["tests"]:
        row["phase_ns"] = dict(setup=1, call=1, teardown=1)
    assert make_baseline(value)["excluded_test_ids"] == ["case.0", "case.1"]
    assert len(make_baseline(measurement(9))["excluded_test_ids"]) == 1


def test_unknown_and_retired_tests_do_not_recalculate_the_frozen_cutoff():
    baseline = make_baseline(measurement())
    selected = {"old": "case.0", "slow": "case.9", "new": "new.case"}
    kept, receipt = filter_partition(selected, ("b" * 64, baseline))
    assert kept == {"old": "case.0", "new": "new.case"}
    assert receipt["excluded_test_ids"] == ["case.9"]
    assert receipt["measured_tests"] == 10 and receipt["baseline_excluded_tests"] == 2
    assert baseline["excluded_test_ids"] == ["case.8", "case.9"]
    assert filter_partition(selected, None) == (selected, None)


def test_explicit_freeze_is_exclusive_and_loading_never_changes_the_baseline(tmp_path):
    (tmp_path / "verification").mkdir()
    source = tmp_path / "measurement.json"
    source.write_bytes(encoded(measurement()))
    expected = freeze(source, tmp_path)
    before = (tmp_path / BASELINE).read_bytes()
    assert load_baseline(tmp_path)[1] == expected
    with pytest.raises(FileExistsError):
        freeze(source, tmp_path)
    assert (tmp_path / BASELINE).read_bytes() == before
    assert not list((tmp_path / "verification").glob(".runtime-baseline-*"))


def test_measurements_require_complete_successful_phases_and_ignore_subreports():
    recorder = RuntimeMeasurements()
    observation = {"nodeid_to_test_id": {"node": "case"}, "workers": ["gw0", "gw1"],
                   "nodeids": ["node"], "tests_run": 1, "suite_passed": True,
                   "pytest_exit_code": 0, "errors": [], "test_outcomes": {"case": "passed"}}
    for phase, duration in (("setup", 0.1), ("call", 0.2), ("teardown", 0.3)):
        recorder.observe("node", phase, duration)
    recorder.observe("node", "call", 1000, subtest=True)
    report = recorder.finish(observation, "a" * 64)
    assert report["tests"][0]["phase_ns"] == dict(setup=100000000, call=200000000, teardown=300000000)
    recorder.observe("node", "call", 0.2)
    with pytest.raises(ValueError): recorder.finish(observation, "a" * 64)


def test_apply_filters_only_the_numbered_group_and_binds_the_actual_selection(tmp_path, monkeypatch):
    from verification_support import apply_rotation as rotation
    from test_apply_thirds import thirds
    from test_apply_rotation import NEXT
    root = tmp_path / "repo"; (root / "verification").mkdir(parents=True)
    measured = measurement(12)
    pairs = {row["nodeid"]: row["test_id"] for row in measured["tests"]}
    registry = thirds(sorted(pairs.values()))
    (root / rotation.REGISTRY).write_text(json.dumps(registry))
    baseline = make_baseline(measured)
    (root / BASELINE).write_bytes(encoded(baseline))
    catalog = {"source_sha256": "bound", "collected_tests": 12, "nodeid_to_test_id": pairs}
    monkeypatch.setattr(rotation, "run_catalog_preflight", lambda r,p: p.write_text(json.dumps(catalog)) or True)
    monkeypatch.setattr(rotation, "commit_context", lambda *a: (NEXT, 1, registry))
    monkeypatch.setattr(rotation, "source_identity", lambda root: "bound")
    group = rotation.select_partition(pairs, registry, 1, registry)
    selected, receipt = filter_partition(group, load_baseline(root))
    outdir = tmp_path / "reports"
    def execute(command, **kwargs):
        actual = (outdir / "nodeids.txt").read_text().splitlines()
        assert actual == list(selected)
        observation = {"observation_format_version": 1, "engine": "pytest",
            "nodeids": actual, "nodeid_to_test_id": selected,
            "test_outcomes": {i: "passed" for i in selected.values()},
            "suite_passed": True, "errors": [], "tests_run": len(actual), "pytest_exit_code": 0,
            "worker_test_counts": {"gw0": len(actual), "gw1": 0}}
        (outdir / "observations.json").write_text(json.dumps(observation))
        return SimpleNamespace(returncode=0)
    report = rotation.run_apply_partition(root, outdir, runner=execute)
    assert report["selected_passed"] and report["full_suite_passed"] is None
    assert report["runtime_filter"] == receipt and report["partition_index"] == 1
    assert report["selection_binding"]["runtime_filter"] == receipt
    assert report["selection_binding"]["format_version"] == 2
    assert report["test_scope"] == "stable_modulo_partition_with_frozen_runtime_filter"


def test_real_full_parallel_gate_records_all_three_native_phases(tmp_path):
    from support.catalog_project import make_catalog_project, execute, NATIVE_IDS, LEGACY_ID
    root = make_catalog_project(tmp_path)
    target = root / "build/timings.json"
    result = execute(root, "run_tests.py", ["--workers", "2",
                     "--runtime-measurement", str(target)])
    assert result.returncode == 0, result.stderr.decode()
    report = json.loads(target.read_text())
    assert report["full_suite_passed"] and report["workers"] == 2
    assert {row["test_id"] for row in report["tests"]} == {*NATIVE_IDS, LEGACY_ID}
    assert all(set(row["phase_ns"]) == {"setup", "call", "teardown"} for row in report["tests"])
    assert all(type(n) is int and n >= 0 for row in report["tests"] for n in row["phase_ns"].values())
    assert make_baseline(report)["excluded_test_ids"] == []


def test_real_failed_full_run_never_publishes_a_calibration(tmp_path):
    from support.catalog_project import make_catalog_project, execute
    root = make_catalog_project(tmp_path)
    (root / "tests/test_failure.py").write_text("def test_failure(): assert False\n")
    target = root / "build/timings.json"
    result = execute(root, "run_tests.py", ["--workers", "2",
                     "--runtime-measurement", str(target)])
    assert result.returncode != 0 and not target.exists()
