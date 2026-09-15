"""Behavior of collection/outcome accounting, not terminal reporting."""

import argparse
import importlib.util
from pathlib import Path

import pytest

from verification_support.pytest_backend import RunLedger, bind_test_ids
from verification import CatalogError, load_catalog

ROOT = Path(__file__).resolve().parents[1]


def ledger(ids=("test_a", "test_b")):
    result = RunLedger()
    result.collect("gw0", ids, [(name, "stable." + name) for name in ids])
    return result


def passed(result, name, worker="gw0"):
    for phase in ("setup", "call", "teardown"):
        result.observe(name, worker, phase, "passed")


def test_complete_parent_phases_are_success():
    result = ledger()
    for name in result.nodeids:
        passed(result, name)
    assert result.result(0).wasSuccessful()
    assert result.snapshot(0)["tests_run"] == 2


def test_worker_collections_use_stable_ids():
    result = ledger()
    result.collect("gw1", result.nodeids, [(n, "stable." + n) for n in result.nodeids])
    passed(result, "test_a")
    passed(result, "test_b", "gw1")
    assert result.result(0).wasSuccessful()
    assert result.snapshot(0)["worker_test_counts"] == {"gw0": 1, "gw1": 1}


def test_missing_test_is_not_success():
    result = ledger()
    passed(result, "test_a")
    assert not result.result(0).wasSuccessful()
    assert result.result(0).outcomes["stable.test_b"] == "not_run"


def test_failed_subtest_is_not_overwritten_by_parent_success():
    result = ledger(("test_a",))
    result.observe("test_a", "gw0", "call", "failed", subtest=True)
    passed(result, "test_a")
    assert result.result(0).outcomes["stable.test_a"] == "failed"
    assert not result.result(0).wasSuccessful()


def test_catalog_legacy_test_identifiers_are_still_bound():
    catalog = load_catalog(ROOT / "verification")
    real_ids = sorted({name for case in catalog.cases for name in case.data["test_ids"]})
    assert bind_test_ids(catalog, real_ids) == tuple(real_ids)
    with pytest.raises(CatalogError):
        bind_test_ids(catalog, real_ids[:-1])


def test_no_collection_does_not_create_success():
    result = RunLedger()
    assert not result.result(0).wasSuccessful()
    assert "missing_collection" in result.errors


@pytest.mark.parametrize("state", ["failed", "error", "skipped", "expected_failure", "unexpected_success"])
def test_nonpassing_subtest_outcomes_cannot_become_a_pass(state):
    result = ledger(("test_a",))
    result.observe("test_a", "gw0", "call", state, subtest=True)
    passed(result, "test_a")
    assert result.result(0).outcomes["stable.test_a"] == state
    assert not result.result(0).wasSuccessful()


@pytest.mark.parametrize("phase", ["setup", "call", "teardown"])
def test_failed_parent_phase_is_not_success(phase):
    result = ledger(("test_a",))
    for value in ("setup", "call", "teardown"):
        result.observe("test_a", "gw0", value, "error" if value == phase else "passed")
    assert not result.result(0).wasSuccessful()


def test_missing_teardown_is_not_success():
    result = ledger(("test_a",))
    result.observe("test_a", "gw0", "setup", "passed")
    result.observe("test_a", "gw0", "call", "passed")
    assert result.result(0).outcomes["stable.test_a"] == "running"


@pytest.mark.parametrize("fault", ["duplicate_collection", "order", "identity", "duplicate_phase",
                                  "multiple_workers", "outside_collection", "worker_crash", "collection_error"])
def test_integrity_faults_cannot_be_success(fault):
    result = ledger()
    for name in result.nodeids:
        passed(result, name)
    if fault == "duplicate_collection":
        result.collect("gw1", ["test_a", "test_a"])
    elif fault == "order":
        result.collect("gw1", ["test_b", "test_a"])
    elif fault == "identity":
        result.collect("gw1", result.nodeids, [(name, "same_alias") for name in result.nodeids])
    elif fault == "duplicate_phase":
        result.observe("test_a", "gw0", "call", "passed")
    elif fault == "multiple_workers":
        result.observe("test_a", "gw1", "call", "passed", subtest=True)
    elif fault == "outside_collection":
        passed(result, "unknown")
    else:
        result.error(fault)
    assert not result.result(0).wasSuccessful()
    assert result.result(0).errors


def test_nonzero_pytest_exit_code_is_not_success():
    result = ledger(("test_a",))
    passed(result, "test_a")
    assert not result.result(3).wasSuccessful()


def test_framework_configuration_is_not_taken_from_inherited_addopts():
    import run_tests
    source = {"PYTEST_ADDOPTS": "-k only_one_test", "PYTEST_PLUGINS": "foreign_plugin",
              "PYTEST_XDIST_WORKER": "gw123", "PYTEST_XDIST_AUTO_NUM_WORKERS": "3", "HOME": "/owned"}
    result = run_tests.test_environment(source)
    assert "PYTEST_ADDOPTS" not in result
    assert "PYTEST_PLUGINS" not in result
    assert "PYTEST_XDIST_WORKER" not in result
    assert result["PYTEST_XDIST_AUTO_NUM_WORKERS"] == "3"
    assert source["PYTEST_ADDOPTS"] == "-k only_one_test"


@pytest.mark.parametrize("value", ["-1", "two", "1.5"])
def test_runner_rejects_invalid_worker_counts(value):
    import run_tests
    with pytest.raises(argparse.ArgumentTypeError):
        run_tests.worker_count(value)
