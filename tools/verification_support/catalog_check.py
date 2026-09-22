"""Collect real test identities without executing test bodies or issuing pass evidence.

Only trusted repository code is imported by pytest during collection. Collection
is not a sandbox and may perform test module import-time work.
"""
import os
from pathlib import Path
import subprocess
import sys

from .catalog import load_catalog
from .common import CatalogError, sha256
from .identity import source_identity
from .publication import evidence_target, publish_report
from .process_environment import test_environment
from .ci_reference import _load_report
from .catalog_contract import collection_contract, validate_preflight_report
from .collection_identity import test_identity


class CollectionProbe:
    """An observer for one collect-only session, not another test scheduler."""
    def __init__(self):
        self.pairs = []
        self.collection_failed = False
        self.tests_started = 0

    def pytest_collection_finish(self, session):
        self.pairs = [(item.nodeid, test_identity(item)) for item in session.items]

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection_failed = True

    def pytest_runtest_logstart(self, nodeid, location):
        self.tests_started += 1


def collect_catalog(root, output):
    """Run in a dedicated interpreter: pytest collection can modify import state."""
    import pytest
    root = Path(root).resolve()
    output = evidence_target(output, root)
    probe = CollectionProbe()
    result = {"format_version": 1, "purpose": "catalog_collection_preflight",
              "catalog_valid": False, "tests_run": 0, "full_suite_passed": None,
              "collected_tests": 0, "nodeid_to_test_id": {}, "missing_test_ids": {},
              "errors": [], "source_sha256": None, "specification_sha256": None,
              "catalog_sha256": None, "collection_exit_code": None}
    try:
        before = source_identity(root)
        result["source_sha256"] = before
        catalog = load_catalog(root / "verification")
        result["catalog_sha256"] = catalog.catalog_sha256
        spec = root / "docs/specification/SpecRoad_Spezifikation.md"
        spec_hash = sha256(spec.read_bytes())
        result["specification_sha256"] = spec_hash
        if catalog.specification_sha256 != spec_hash:
            raise CatalogError("Specification binding mismatch")
        # Explicitly clear the normal parallel addopts: only collection, no
        # test bodies, setup/teardown fixtures or worker processes are started.
        code = int(pytest.main(["-o", "addopts=", "--disable-plugin-autoload",
                               "-p", "no:cacheprovider", "-p", "no:doctest",
                               "--collect-only", "-qq", str(root / "tests")],
                              plugins=[probe]))
        result["collection_exit_code"] = code
        result.update(collection_contract(catalog, probe.pairs))
        result["tests_run"] = probe.tests_started
        if code != 0 or probe.collection_failed or probe.tests_started:
            result["errors"].append("collection_not_completed")
        if (source_identity(root) != before or sha256(spec.read_bytes()) != spec_hash
                or load_catalog(root / "verification").catalog_sha256 != catalog.catalog_sha256):
            result["errors"].append("inputs_changed_during_collection")
    except (CatalogError, OSError, ValueError, TypeError, RecursionError):
        result["errors"].append("invalid_catalog_or_collection")
    result["catalog_valid"] = not result["errors"]
    publish_report(output, root, result)
    return result


def run_catalog_preflight(root, output, *, runner=None, environment=None):
    """Require a successful, fresh collection report before any selected gate."""
    root = Path(root).resolve()
    target = evidence_target(output, root)
    before = source_identity(root)
    runner = subprocess.run if runner is None else runner
    command = [sys.executable, "-I", "-B", str(root / "tools/check_test_catalog.py"),
               "--output", str(target)]
    try:
        code = runner(command, cwd=root,
                      env=test_environment(os.environ if environment is None else environment),
                      stdin=subprocess.DEVNULL, check=False).returncode
        report = _load_report(target)
        if code != 0 or source_identity(root) != before:
            return False
        return validate_preflight_report(root, report, before)
    except (CatalogError, OSError, ValueError, TypeError, AttributeError, RecursionError):
        return False


