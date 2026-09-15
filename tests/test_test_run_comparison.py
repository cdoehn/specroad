"""Verification of current-run data, not human-readable test reports."""

from copy import deepcopy
import uuid

import pytest

from compare_test_runs import ComparisonError, compare_reports


def report():
    return {
        "report_format_version": 2, "purpose": "development_behavior_evidence",
        "suite_passed": True, "tests_run": 1,
        "test_outcomes": {"stable.a": "passed"}, "run_id": str(uuid.uuid4()),
        **{name: "a" * 64 for name in ("tool_build_sha256", "specification_sha256", "catalog_sha256", "platform_sha256")},
        "observation": {
            "nodeids": ["test.py::test_a"], "nodeid_to_test_id": {"test.py::test_a": "stable.a"},
            "test_outcomes": {"stable.a": "passed"}, "suite_passed": True, "errors": [],
            "pytest_exit_code": 0, "tests_run": 1, "worker_test_counts": {"main": 1},
        },
    }


def test_equivalent_runs_may_use_different_workers():
    first, second = report(), report()
    second["observation"]["worker_test_counts"] = {"gw0": 1, "gw1": 0}
    assert compare_reports([first, second]) == {"equivalent": True, "runs": 2, "tests": 1}


@pytest.mark.parametrize("fault", ["failed", "missing", "duplicate", "source", "repeat", "worker_count", "identity"])
def test_non_equivalent_or_incomplete_runs_are_rejected(fault):
    first, second = report(), report()
    if fault == "failed":
        second["suite_passed"] = False
    elif fault == "missing":
        second["observation"]["nodeids"] = []
    elif fault == "duplicate":
        second["observation"]["nodeids"] *= 2
    elif fault == "source":
        second["tool_build_sha256"] = "b" * 64
    elif fault == "repeat":
        second["run_id"] = first["run_id"]
    elif fault == "worker_count":
        second["observation"]["worker_test_counts"] = {"gw0": 2}
    elif fault == "identity":
        second["observation"]["nodeid_to_test_id"] = {}
    with pytest.raises(ComparisonError):
        compare_reports([first, second])


def test_single_run_is_not_a_parallel_serial_comparison():
    with pytest.raises(ComparisonError):
        compare_reports([report()])
