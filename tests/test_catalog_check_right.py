"""Controlled framework errors, freshness and reports, not rendered diagnostics."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from support.catalog_project import make_catalog_project, execute, check, effects
from verification_support.catalog import load_catalog
from verification_support.catalog_check import (collection_contract, run_catalog_preflight,
                                                validate_preflight_report)
from verification_support.identity import source_identity


@pytest.mark.parametrize("workers", ["0", "2", "4"])
def test_invalid_full_catalog_aborts_before_scheduling_and_preserves_failure_report(tmp_path, workers):
    # Small fixture gates, not serial executions of the full product suite.
    root = make_catalog_project(tmp_path, ids=["test_subject.test_native"])
    output = root / "build/failure.json"
    observed = root / "build/observation.json"
    proc = execute(root, "run_tests.py", ["--workers", workers,
        "--evidence", str(output), "--observations", str(observed)])
    assert proc.returncode != 0 and not effects(root)
    report = json.loads(output.read_text())
    observation = json.loads(observed.read_text())
    assert report["purpose"] == "development_verification_failure"
    assert report["suite_passed"] is False and report["release_approved"] is False
    assert report["tests_run"] == observation["tests_run"] == 0
    assert "verification_contract_error" in observation["errors"]
    assert "pytest_internal_error" not in observation["errors"]


def test_preflight_reports_source_changes_during_collection(tmp_path):
    root = make_catalog_project(tmp_path)
    (root / "tests/test_mutate.py").write_text(
        'from pathlib import Path\nPath("src/specroad/changed.py").write_text("# changed")\n')
    code, report = check(root)
    assert code == 4 and not report["catalog_valid"]
    assert "inputs_changed_during_collection" in report["errors"] and not effects(root)


def test_inherited_pytest_filters_are_removed_in_collection_child(tmp_path):
    root = make_catalog_project(tmp_path)
    code, report = check(root, environment={"PYTEST_ADDOPTS": "-k impossible_selection",
                                          "PYTEST_PLUGINS": "does_not_exist"})
    assert code == 0 and report["collected_tests"] == 4 and report["tests_run"] == 0


def test_existing_report_is_never_overwritten(tmp_path):
    root = make_catalog_project(tmp_path)
    path = root / "build/preflight.json"
    path.write_bytes(b"preserve")
    proc = execute(root, "check_test_catalog.py", ["--output", str(path)])
    assert proc.returncode == 4
    assert path.read_bytes() == b"preserve" and not effects(root)


def test_source_target_cannot_be_used_for_report(tmp_path):
    root = make_catalog_project(tmp_path)
    target = root / "tests/new.json"
    proc = execute(root, "check_test_catalog.py", ["--output", str(target)])
    assert proc.returncode == 4 and not target.exists() and not effects(root)


def test_linked_report_parent_is_refused(tmp_path):
    root = make_catalog_project(tmp_path)
    (root / "build/link").symlink_to(root / "build", target_is_directory=True)
    proc = execute(root, "check_test_catalog.py", ["--output", str(root / "build/link/report.json")])
    assert proc.returncode == 4 and not (root / "build/report.json").exists()


def test_missing_native_reference_in_unselected_file_blocks_selected_gate(tmp_path):
    root = make_catalog_project(tmp_path, ids=["tests/test_unselected.py::test_removed"])
    proc = execute(root, "run_selected_tests.py", ["--test-file", "tests/test_subject.py",
        "--expected-tests", "4", "--outdir", str(root / "build/selected")])
    assert proc.returncode == 4 and not effects(root)


@pytest.fixture
def valid_report(tmp_path):
    root = make_catalog_project(tmp_path)
    assert check(root)[0] == 0
    return root, json.loads((root / "build/preflight.json").read_text())


@pytest.mark.parametrize("key,value", [
    ("format_version", True), ("collection_exit_code", False), ("tests_run", False),
    ("tests_run", 1), ("collected_tests", True), ("collected_tests", 0),
    ("collected_tests", 3), ("full_suite_passed", True), ("catalog_valid", 1),
    ("errors", ["failure"]), ("missing_test_ids", {"SR-TC-0001": ["missing"]}),
    ("catalog_sha256", "f" * 64), ("specification_sha256", "f" * 64),
    ("source_sha256", "f" * 64), ("nodeid_to_test_id", {}),
    ("purpose", "development_behavior_evidence"),
])
def test_malformed_or_forged_preflight_is_not_accepted(valid_report, key, value):
    root, report = valid_report
    report[key] = value
    assert not validate_preflight_report(root, report, source_identity(root))


def test_missing_fields_cannot_claim_no_tests_ran(valid_report):
    root, report = valid_report
    report.pop("full_suite_passed")
    assert not validate_preflight_report(root, report, source_identity(root))


def test_report_does_not_authorize_changed_source(valid_report):
    root, report = valid_report
    (root / "tests/test_new.py").write_text("def test_new(): pass\n")
    def runner(command, **kwargs):
        Path(command[-1]).write_text(json.dumps(report))
        return SimpleNamespace(returncode=0)
    assert not run_catalog_preflight(root, root / "build/stale.json", runner=runner)


def test_spawn_error_cannot_start_selected_tests(tmp_path):
    root = make_catalog_project(tmp_path)
    calls = []
    def runner(*args, **kwargs):
        calls.append(args)
        raise OSError("cannot start")
    assert not run_catalog_preflight(root, root / "build/missing.json", runner=runner)
    assert len(calls) == 1 and not effects(root)


@pytest.mark.parametrize("pairs", [["ab"], [["a"]], [["a", "b", "c"]], [["", "b"]], [["a", 1]]])
def test_invalid_pair_shapes_are_refused(tmp_path, pairs):
    root = make_catalog_project(tmp_path)
    with pytest.raises(ValueError):
        collection_contract(load_catalog(root / "verification"), pairs)


@pytest.mark.parametrize("workers", ["2", "4"])
def test_wrong_expected_count_stops_workers_without_running_test_bodies(tmp_path, workers):
    root = make_catalog_project(tmp_path)
    output = root / "build/failure.json"
    observed = root / "build/observation.json"
    proc = execute(root, "run_tests.py", ["--workers", workers, "--expected-tests", "5",
        "--evidence", str(output), "--observations", str(observed)])
    assert proc.returncode != 0 and not effects(root)
    report = json.loads(output.read_text())
    observation = json.loads(observed.read_text())
    assert report["suite_passed"] is False and report["release_approved"] is False
    assert report["tests_run"] == observation["tests_run"] == 0
    assert "unexpected_test_count" in observation["errors"]
    assert "pytest_internal_error" not in observation["errors"]


def test_real_four_worker_gate_accepts_mixed_native_and_legacy_identities(tmp_path):
    root = make_catalog_project(tmp_path)
    output = root / "build/evidence.json"
    observed = root / "build/observation.json"
    proc = execute(root, "run_tests.py", ["--workers", "4", "--expected-tests", "4",
        "--evidence", str(output), "--observations", str(observed)])
    assert proc.returncode == 0
    report = json.loads(output.read_text())
    observation = json.loads(observed.read_text())
    assert report["suite_passed"] is True and report["release_approved"] is False
    assert report["tests_run"] == observation["tests_run"] == 4
    assert not observation["errors"] and len(effects(root)) == 4


def test_small_ci_fixture_preserves_full_parallel_evidence(tmp_path):
    root = make_catalog_project(tmp_path)
    assert check(root)[0] == 0
    outdir = root / "build/ci-reference"
    proc = execute(root, "run_ci_tests.py", ["--workers", "4", "--outdir", str(outdir)],
                   environment={"GITHUB_ACTIONS": "true"})
    assert proc.returncode == 0
    report = json.loads((outdir / "summary.json").read_text())
    assert report["suite_passed"] and report["comparison"] is None
    assert [item["workers"] for item in report["checks"]] == [4]
    evidence = json.loads((outdir / "parallel-evidence.json").read_text())
    assert evidence["tests_run"] == 4
    assert not (outdir / "serial-evidence.json").exists()
