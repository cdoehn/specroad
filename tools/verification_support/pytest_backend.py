"""pytest hooks and xdist transport; only the controller publishes evidence."""

from .common import CatalogError
from .outcomes import RunLedger, bind_test_ids

import importlib.metadata
import json
from pathlib import Path
import sys
import unittest
import uuid

import pytest

from .catalog import load_catalog
from .common import json_bytes, sha256
from .evidence import make_report
from .identity import platform_identity, source_identity
from .publication import evidence_target, publish_report


ROOT = Path(__file__).resolve().parents[2]


def test_identity(item):
    """Preserve existing unittest IDs; use native nodeids for new pytest tests."""
    cls = getattr(item, "cls", None)
    if isinstance(cls, type) and issubclass(cls, unittest.TestCase):
        return cls.__module__ + "." + cls.__qualname__ + "." + item.name
    return item.nodeid


def pytest_addoption(parser):
    group = parser.getgroup("specroad-development")
    group.addoption("--sr-gate", action="store_true", help="Verify the complete behavior catalog")
    group.addoption("--sr-evidence", type=Path, help="Exclusive path for bound development evidence")
    group.addoption("--sr-observations", type=Path, help="Exclusive path for test-run observations")
    group.addoption("--sr-expected-tests", type=int, help="Required number of collected tests")


class VerificationSession:
    def __init__(self, config):
        self.config = config
        self.worker = hasattr(config, "workerinput")
        self.worker_id = config.workerinput["workerid"] if self.worker else "main"
        self.ledger = RunLedger()
        self.gate = config.getoption("sr_gate") or config.getoption("sr_evidence") is not None
        self.expected = config.getoption("sr_expected_tests")
        self.evidence = config.getoption("sr_evidence")
        self.observations = config.getoption("sr_observations")
        self.catalog = None
        self.specification = ROOT / "docs/specification/SpecRoad_Spezifikation.md"
        self.binding = None
        self.required_ids = set()
        if self.worker:
            self.required_ids = set(config.workerinput.get("sr_required_ids", []))
            return
        if self.expected is not None and self.expected <= 0:
            raise CatalogError("Expected test count must be positive")
        for target in (self.evidence, self.observations):
            if target is not None:
                evidence_target(target, ROOT)
        if (self.evidence is not None and self.observations is not None
                and self.evidence.absolute() == self.observations.absolute()):
            raise CatalogError("Evidence and observations need separate destinations")
        if self.gate:
            if config.getoption("collectonly") or config.getoption("keyword") or config.getoption("markexpr"):
                raise CatalogError("A full behavior gate cannot select or only collect tests")
            scopes = [Path(value).absolute() for value in config.args]
            if scopes != [ROOT / "tests"] or config.getoption("ignore") or config.getoption("ignore_glob"):
                raise CatalogError("A full behavior gate must collect the entire tests directory")
            self.catalog = load_catalog(ROOT / "verification")
            if sha256(self.specification.read_bytes()) != self.catalog.specification_sha256:
                raise CatalogError("Catalog is not bound to the current specification bytes")
            if any(case.data["evidence_kind"] != "specroad-dev-pytest-v1" for case in self.catalog.cases):
                raise CatalogError("Current pytest evidence needs migrated manifests")
            self.required_ids = {name for case in self.catalog.cases for name in case.data["test_ids"]}
            self.source = source_identity(ROOT)
            self.runtime = platform_identity()
            self.execution = {"engine": "pytest", "pytest": pytest.__version__,
                              "pytest_xdist": _version("pytest-xdist"),
                              "workers": config.getoption("numprocesses", default=0),
                              "distribution": config.getoption("dist", default="no"),
                              "test_timeout": None, "suite_timeout": None}
            self.binding = {"run_id": str(uuid.uuid4()), "tool_build_sha256": self.source,
                            "platform_sha256": sha256(json_bytes(self.runtime)),
                            "configuration_sha256": sha256(json_bytes(self.execution))}

    def collection(self, items):
        pairs = [(item.nodeid, test_identity(item)) for item in items]
        nodeids = [row[0] for row in pairs]
        ids = [row[1] for row in pairs]
        self.ledger.collect(self.worker_id, nodeids, pairs)
        if self.worker:
            self.config.workeroutput["sr_collection"] = pairs
        if self.gate and (not self.required_ids <= set(ids) or len(ids) != len(set(ids))):
            self.ledger.error("catalog_binding_invalid")
            if self.worker:
                self.config.workeroutput["sr_collection_errors"] = list(self.ledger.errors)
            raise pytest.UsageError("Catalog names missing or ambiguous collected tests")
        if self.expected is not None and len(ids) != self.expected:
            self.ledger.error("unexpected_test_count")
            if self.worker:
                self.config.workeroutput["sr_collection_errors"] = list(self.ledger.errors)
            raise pytest.UsageError("Discovered suite size differs from the behavior gate")
        for item, (_, alias) in zip(items, pairs):
            item.user_properties.extend((("sr_test_id", alias), ("sr_worker", self.worker_id)))


def _version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def pytest_configure(config):
    try:
        config._specroad_verification = VerificationSession(config)
    except (CatalogError, OSError, ValueError) as error:
        raise pytest.UsageError(str(error)) from error


@pytest.hookimpl(tryfirst=True)
def pytest_collection_finish(session):
    # Validate BEFORE xdist sends collectionfinish to its controller. Sending
    # IDs first can cause it to schedule an item for a worker already exiting.
    try:
        session.config._specroad_verification.collection(session.items)
    except pytest.UsageError:
        # A worker must announce a deliberate stop to xdist, not disappear as
        # though it had completed its queue. Keep the real binding error and
        # let the controller perform its normal coordinated shutdown.
        session.shouldstop = "SpecRoad collection contract rejected"
        raise


@pytest.hookimpl(optionalhook=True)
def pytest_configure_node(node):
    state = node.config._specroad_verification
    node.workerinput["sr_required_ids"] = sorted(state.required_ids)


@pytest.hookimpl(optionalhook=True)
def pytest_xdist_node_collection_finished(node, ids):
    state = node.config._specroad_verification
    state.ledger.collect(node.gateway.id, ids)
    if state.expected is not None and len(ids) != state.expected:
        state.ledger.error("unexpected_test_count")


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node, error):
    state = node.config._specroad_verification
    output = getattr(node, "workeroutput", {}) or {}
    pairs = output.get("sr_collection")
    if output.get("exitstatus") != 0:
        state.ledger.error("worker_nonzero_exit")
    if pairs is None:
        state.ledger.error("missing_worker_collection")
    else:
        state.ledger.collect(node.gateway.id, [row[0] for row in pairs], pairs)
    for code in output.get("sr_collection_errors", ()):
        state.ledger.error(code)
    if error is not None:
        state.ledger.error("worker_crash")


class ReportObserver:
    def __init__(self, state):
        self.state = state

    def pytest_collectreport(self, report):
        if report.failed:
            self.state.ledger.error("collection_error")

    def pytest_deselected(self, items):
        if items and self.state.gate:
            self.state.ledger.error("deselected_tests")

    def pytest_internalerror(self, excrepr, excinfo):
        self.state.ledger.error("pytest_internal_error")

    def pytest_keyboard_interrupt(self, excinfo):
        self.state.ledger.error("interrupted")

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_logreport(self, report):
        # SubtestReport exposes a context in pytest >=9; do not count its call
        # report as a second execution of the parent test. No output is parsed.
        subtest = hasattr(report, "context")
        properties = dict(report.user_properties)
        worker = properties.get("sr_worker", self.state.worker_id)
        alias = properties.get("sr_test_id")
        if alias is not None:
            old = self.state.ledger.aliases.get(report.nodeid)
            if old is not None and old != alias:
                self.state.ledger.error("conflicting_report_identity")
            self.state.ledger.aliases[report.nodeid] = alias
        if hasattr(report, "wasxfail"):
            outcome = "unexpected_success" if report.passed else "expected_failure"
        elif report.failed:
            outcome = "failed" if report.when == "call" else "error"
        elif report.skipped:
            outcome = "skipped"
        else:
            outcome = "passed"
        self.state.ledger.observe(report.nodeid, worker, report.when, outcome, subtest=subtest)


def pytest_sessionstart(session):
    state = session.config._specroad_verification
    session.config.pluginmanager.register(ReportObserver(state), "specroad-report-observer")


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    state = session.config._specroad_verification
    if state.worker:
        return
    try:
        observation = state.ledger.snapshot(exitstatus)
        if state.gate:
            discovered = bind_test_ids(state.catalog, (state.ledger.aliases.get(n, n) for n in state.ledger.nodeids))
            if (source_identity(ROOT) != state.source
                    or sha256(state.specification.read_bytes()) != state.catalog.specification_sha256):
                raise CatalogError("Inputs changed during testing; no current pass evidence")
            result = state.ledger.result(exitstatus)
            report = make_report(state.catalog, state.binding, result, discovered)
            report.update(report_format_version=2, runtime=state.runtime,
                          execution=state.execution, observation=observation)
            if state.evidence is not None:
                publish_report(state.evidence, ROOT, report)
            print(json.dumps({"tests_run": report["tests_run"], "suite_passed": report["suite_passed"],
                              "requirement_counts": report["requirement_counts"], "release_approved": False},
                             sort_keys=True))
            if not report["suite_passed"] and session.exitstatus == 0:
                session.exitstatus = pytest.ExitCode.TESTS_FAILED
    except (CatalogError, OSError, ValueError) as error:
        print("Development verification failed: " + str(error), file=sys.stderr)
        session.exitstatus = pytest.ExitCode.USAGE_ERROR
        state.ledger.error("verification_contract_error")
        observation = state.ledger.snapshot(session.exitstatus)
        # Failure diagnostics are not development pass evidence and cannot be
        # compared as a successful serial/parallel run. Preserve real causes
        # even when binding fails before the first test.
        if state.evidence is not None:
            failure = {"report_format_version": 1,
                       "purpose": "development_verification_failure",
                       "suite_passed": False, "release_approved": False,
                       "tests_run": observation["tests_run"],
                       "error": {"code": "verification_contract_error", "detail": str(error)},
                       "observation": observation}
            try:
                publish_report(state.evidence, ROOT, failure)
            except (CatalogError, OSError, ValueError):
                print("Could not publish verification failure report.", file=sys.stderr)
    if state.observations is not None:
        try:
            publish_report(state.observations, ROOT, observation)
        except (CatalogError, OSError, ValueError) as error:
            print("Could not publish test observations: " + str(error), file=sys.stderr)
            session.exitstatus = pytest.ExitCode.USAGE_ERROR
