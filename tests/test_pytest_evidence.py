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
