"""Real collected IDs, never a manifest's self-declared test inventory."""
from pathlib import Path
import json
from types import SimpleNamespace
import pytest

from support.catalog_project import (make_catalog_project, execute, check, effects,
                                     NATIVE_IDS, LEGACY_ID)
from verification_support.catalog_check import collection_contract, run_catalog_preflight
from verification_support.catalog import load_catalog
from verification_support.identity import source_identity


def test_actual_collection_preserves_native_parameter_and_unittest_ids(tmp_path):
    root = make_catalog_project(tmp_path)
    before = source_identity(root)
    code, report = check(root)
    assert code == 0 and report["catalog_valid"]
    assert set(report["nodeid_to_test_id"].values()) == {*NATIVE_IDS, LEGACY_ID}
    assert report["collected_tests"] == 4
    assert report["tests_run"] == 0 and report["full_suite_passed"] is None
    assert not effects(root) and source_identity(root) == before


def test_dotted_native_reference_is_not_guessed_or_accepted(tmp_path):
    root = make_catalog_project(tmp_path, ids=["test_subject.test_native"])
    code, report = check(root)
    assert code == 4 and not report["catalog_valid"]
    assert report["missing_test_ids"] == {"SR-TC-0001": ["test_subject.test_native"]}
    assert report["errors"] == ["unavailable_test_reference"]
    assert not effects(root)


def test_parametrized_base_reference_does_not_replace_concrete_variants(tmp_path):
    root = make_catalog_project(tmp_path, ids=["tests/test_subject.py::test_parameter"])
    code, report = check(root)
    assert code == 4 and report["missing_test_ids"]
    assert report["tests_run"] == 0 and not effects(root)


def test_missing_function_is_reported_without_execution(tmp_path):
    root = make_catalog_project(tmp_path, ids=["tests/test_subject.py::test_removed"])
    code, report = check(root)
    assert code == 4 and not report["catalog_valid"]
    assert report["missing_test_ids"]["SR-TC-0001"] == ["tests/test_subject.py::test_removed"]
    assert not effects(root)


def test_collection_error_is_not_hidden_by_remaining_valid_tests(tmp_path):
    root = make_catalog_project(tmp_path)
    (root / "tests/test_broken.py").write_text("raise ValueError('collection failure')\n")
    code, report = check(root)
    assert code == 4 and not report["catalog_valid"]
    assert "collection_not_completed" in report["errors"] and not effects(root)


def test_invalid_specification_binding_stops_before_importing_tests(tmp_path):
    root = make_catalog_project(tmp_path)
    (root / "docs/specification/SpecRoad_Spezifikation.md").write_text("changed")
    code, report = check(root)
    assert code == 4 and not report["catalog_valid"]
    assert report["collected_tests"] == 0 and not effects(root)


def test_all_missing_references_are_reported_together(tmp_path):
    root = make_catalog_project(tmp_path, ids=["missing.z", "missing.a"])
    code, report = check(root)
    assert code == 4 and report["missing_test_ids"] == {"SR-TC-0001": ["missing.a", "missing.z"]}


def test_selected_entrypoint_refuses_invalid_catalog_before_test_bodies(tmp_path):
    root = make_catalog_project(tmp_path, ids=["test_subject.test_native"])
    outdir = root / "build/selection"
    proc = execute(root, "run_selected_tests.py", ["--test-file", "tests/test_subject.py",
        "--expected-tests", "4", "--workers", "2", "--outdir", str(outdir)])
    assert proc.returncode == 4 and not outdir.exists() and not effects(root)
    assert json.loads((root / "build/selection-catalog.json").read_text())["catalog_valid"] is False


def test_selected_entrypoint_runs_only_selected_tests_after_preflight(tmp_path):
    root = make_catalog_project(tmp_path)
    (root / "tests/test_unselected.py").write_text(
        'from pathlib import Path\ndef test_unselected():\n    Path("build/unselected_started").touch()\n')
    outdir = root / "build/selected"
    proc = execute(root, "run_selected_tests.py", ["--test-file", "tests/test_subject.py",
        "--expected-tests", "4", "--workers", "2", "--outdir", str(outdir)])
    assert proc.returncode == 0
    report = json.loads((outdir / "selection.json").read_text())
    preflight = json.loads((root / "build/selected-catalog.json").read_text())
    assert report["selected_passed"] and report["full_suite_passed"] is None
    assert preflight["collected_tests"] == 5 and preflight["tests_run"] == 0
    assert effects(root) == ["fixture_started", "legacy_started", "native_started", "parameter_started"]


def test_preflight_requires_fresh_actual_report(tmp_path):
    root = make_catalog_project(tmp_path)
    assert run_catalog_preflight(root, root / "build/run.json")
    with pytest.raises(ValueError):
        run_catalog_preflight(root, root / "build/run.json")


@pytest.mark.parametrize("worker_code", [1, 4, -9])
def test_nonzero_collector_exit_cannot_be_hidden_by_valid_report(tmp_path, worker_code):
    root = make_catalog_project(tmp_path)
    _, valid = check(root)
    def runner(command, **kwargs):
        Path(command[-1]).write_text(json.dumps(valid))
        return SimpleNamespace(returncode=worker_code)
    assert not run_catalog_preflight(root, root / "build/new.json", runner=runner)


def test_missing_collector_report_is_not_success(tmp_path):
    root = make_catalog_project(tmp_path)
    assert not run_catalog_preflight(root, root / "build/none.json",
        runner=lambda *a, **k: SimpleNamespace(returncode=0))


def test_ambiguous_collected_identity_is_rejected(tmp_path):
    root = make_catalog_project(tmp_path)
    contract = collection_contract(load_catalog(root / "verification"), [("a", "shared"), ("b", "shared")])
    assert "ambiguous_test_identity" in contract["errors"]


def test_empty_collection_is_not_a_valid_catalog(tmp_path):
    root = make_catalog_project(tmp_path)
    assert "empty_collection" in collection_contract(load_catalog(root / "verification"), [])["errors"]


def test_full_gate_with_small_real_catalog_keeps_native_and_legacy_outcomes(tmp_path):
    root = make_catalog_project(tmp_path)
    path = root / "build/full-evidence.json"
    proc = execute(root, "run_tests.py", ["--workers", "2", "--evidence", str(path)])
    assert proc.returncode == 0
    report = json.loads(path.read_text())
    assert report["suite_passed"] and report["tests_run"] == 4
    assert report["release_approved"] is False
    assert set(report["test_outcomes"]) == {*NATIVE_IDS, LEGACY_ID}
