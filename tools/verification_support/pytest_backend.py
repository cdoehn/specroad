"""Framework-independent collection and outcome accounting for one test run."""

from dataclasses import dataclass

from .common import CatalogError


RANK = {"not_run": 0, "running": 1, "passed": 2, "expected_failure": 3,
        "skipped": 4, "unexpected_success": 5, "failed": 6, "error": 7}


def bind_test_ids(catalog, test_ids):
    """Bind trusted collected identifiers, never import names from manifest data."""
    ids = tuple(test_ids)
    if not ids or any(not isinstance(name, str) or not name for name in ids) or len(ids) != len(set(ids)):
        raise CatalogError("Test discovery is empty or ambiguous")
    available = set(ids)
    for case in catalog.cases:
        if not set(case.data["test_ids"]) <= available:
            raise CatalogError("Manifest names an unavailable real test: " + case.data["test_case_id"])
    return ids


@dataclass
class ObservedExecution:
    outcomes: dict
    testsRun: int
    exit_code: int
    errors: tuple

    def wasSuccessful(self):
        return (self.exit_code == 0 and not self.errors and bool(self.outcomes)
                and all(value == "passed" for value in self.outcomes.values()))


class RunLedger:
    """The controller observes reports; xdist alone schedules and executes tests."""

    def __init__(self):
        self.collections = {}
        self.aliases = {}
        self.phases = {}
        self.worst = {}
        self.owners = {}
        self.errors = []
        self.workers = set()
        self.exit_code = 0

    def error(self, code):
        if code not in self.errors:
            self.errors.append(code)

    def collect(self, worker, nodeids, pairs=None):
        ids = tuple(nodeids)
        self.workers.add(worker)
        if not ids or len(ids) != len(set(ids)):
            self.error("empty_or_duplicate_collection")
        if self.collections and ids != next(iter(self.collections.values())):
            self.error("inconsistent_worker_collection")
        if worker in self.collections and self.collections[worker] != ids:
            self.error("worker_changed_collection")
        self.collections[worker] = ids
        if pairs is not None:
            rows = tuple(tuple(row) for row in pairs)
            if (any(len(row) != 2 or any(not isinstance(value, str) or not value for value in row)
                    for row in rows) or tuple(row[0] for row in rows) != ids
                    or len({row[1] for row in rows}) != len(rows)):
                self.error("ambiguous_test_identity")
                return
            for nodeid, alias in rows:
                if nodeid in self.aliases and self.aliases[nodeid] != alias:
                    self.error("inconsistent_test_identity")
                self.aliases[nodeid] = alias

    def observe(self, nodeid, worker, phase, state, *, subtest=False):
        if phase not in ("setup", "call", "teardown") or state not in RANK:
            self.error("invalid_test_report")
            return
        self.workers.add(worker)
        if nodeid in self.owners and self.owners[nodeid] != worker:
            self.error("test_executed_by_multiple_workers")
        self.owners[nodeid] = worker
        phases = self.phases.setdefault(nodeid, {})
        if not subtest:
            if phase in phases:
                self.error("duplicate_test_phase")
            phases[phase] = state
        previous = self.worst.get(nodeid, "not_run")
        if RANK[state] > RANK[previous]:
            self.worst[nodeid] = state

    @property
    def nodeids(self):
        return next(iter(self.collections.values()), ())

    def result(self, exit_code):
        self.exit_code = int(exit_code)
        if not self.collections:
            self.error("missing_collection")
        expected = set(self.nodeids)
        if set(self.phases) - expected:
            self.error("report_outside_collection")
        if set(self.aliases) != expected:
            self.error("incomplete_test_identity")
        outcomes = {}
        for nodeid in self.nodeids:
            alias = self.aliases.get(nodeid, nodeid)
            state = self.worst.get(nodeid, "not_run")
            phases = self.phases.get(nodeid, {})
            if state == "passed" and (set(phases) != {"setup", "call", "teardown"}
                                       or any(value != "passed" for value in phases.values())):
                state = "running"
            if alias in outcomes:
                self.error("duplicate_result_identity")
            outcomes[alias] = state
        return ObservedExecution(outcomes, len(expected & self.phases.keys()),
                                 int(exit_code), tuple(self.errors))

    def snapshot(self, exit_code):
        result = self.result(exit_code)
        return {
            "observation_format_version": 1,
            "engine": "pytest",
            "nodeids": list(self.nodeids),
            "nodeid_to_test_id": dict(sorted(self.aliases.items())),
            "test_outcomes": dict(sorted(result.outcomes.items())),
            "tests_run": result.testsRun,
            "suite_passed": result.wasSuccessful(),
            "pytest_exit_code": int(exit_code),
            "workers": sorted(self.workers),
            "worker_test_counts": {worker: sum(owner == worker for owner in self.owners.values())
                                   for worker in sorted(self.workers)},
            "errors": list(result.errors),
        }
# ---- pytest and xdist integration: only the controller publishes evidence. ----

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
            raise pytest.UsageError("Catalog names missing or ambiguous collected tests")
        if self.expected is not None and len(ids) != self.expected:
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


def pytest_collection_finish(session):
    session.config._specroad_verification.collection(session.items)


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
    pairs = getattr(node, "workeroutput", {}).get("sr_collection")
    if pairs is None:
        state.ledger.error("missing_worker_collection")
    else:
        state.ledger.collect(node.gateway.id, [row[0] for row in pairs], pairs)
    if error is not None:
        state.ledger.error("worker_crash")


class ReportObserver:
    def __init__(self, state):
        self.state = state

    def pytest_collectreport(self, report):
        if report.failed:
            self.state.ledger.error("collection_error")

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
        if state.observations is not None:
            publish_report(state.observations, ROOT, observation)
    except (CatalogError, OSError, ValueError) as error:
        print("Development verification failed: " + str(error), file=sys.stderr)
        session.exitstatus = pytest.ExitCode.USAGE_ERROR
