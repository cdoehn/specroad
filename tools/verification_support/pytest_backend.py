"""pytest hooks and xdist transport; only the controller publishes evidence."""

from .common import CatalogError
from .outcomes import RunLedger, bind_test_ids
from .collection_identity import test_identity
from .runtime_baseline import RuntimeMeasurements
from .runtime_store import TimingStore
from .runtime_history import RuntimeHistory
from .ci_reference import _load_report

import importlib.metadata
import json
from pathlib import Path
import sys
import uuid
import sqlite3

import pytest

from .catalog import load_catalog
from .common import json_bytes, sha256
from .evidence import make_report
from .identity import platform_identity, source_identity
from .publication import evidence_target, publish_report


ROOT = Path(__file__).resolve().parents[2]




def pytest_addoption(parser):
    group = parser.getgroup("specroad-development")
    group.addoption("--sr-gate", action="store_true", help="Verify the complete behavior catalog")
    group.addoption("--sr-evidence", type=Path, help="Exclusive path for bound development evidence")
    group.addoption("--sr-observations", type=Path, help="Exclusive path for test-run observations")
    group.addoption("--sr-runtimes", type=Path, help="One explicit full parallel timing measurement")
    group.addoption("--sr-runtime-journal", type=Path)
    group.addoption("--sr-timing-request", type=Path)
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
        self.runtimes = config.getoption("sr_runtimes")
        self.runtime_measurements = RuntimeMeasurements() if self.runtimes is not None and not self.worker else None
        self.timing_store = None
        self.timing_run = None
        self.timing_request = None
        self.history = None
        self.history_run = None
        self.history_root = Path(config.rootpath).resolve()
        self.history_source = None
        self.catalog = None
        self.specification = ROOT / "docs/specification/SpecRoad_Spezifikation.md"
        self.binding = None
        self.required_ids = set()
        if self.worker:
            self.required_ids = set(config.workerinput.get("sr_required_ids", []))
            if not config.getoption('collectonly'):
                self.history = RuntimeHistory(self.history_root)
                self.history_run = config.workerinput['sr_history_run']
            return
        if self.expected is not None and self.expected <= 0:
            raise CatalogError("Expected test count must be positive")
        if self.runtimes is not None and not self.gate:
            raise CatalogError("Runtime calibration requires an explicit complete gate")
        targets = [p.absolute() for p in (self.evidence, self.observations, self.runtimes) if p is not None]
        if len(set(targets)) != len(targets):
            raise CatalogError("Runtime, evidence and observations need separate destinations")
        for target in (self.evidence, self.observations, self.runtimes):
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

        journal = config.getoption("sr_runtime_journal")
        request = config.getoption("sr_timing_request")
        if (journal is None) != (request is None):
            raise CatalogError("Timing journal and request must be supplied together")
        if self.runtimes is not None and journal is None:
            raise CatalogError("Runtime calibration requires durable phase storage")
        if journal is not None:
            value = _load_report(request)
            if (set(value) != {"format_version", "binding", "selected"}
                    or value["format_version"] != 1 or not value["selected"]
                    or value["binding"]["source_sha256"] != source_identity(ROOT)
                    or value["binding"]["workers"] != config.getoption("numprocesses")
                    or self.expected != len(value["selected"])
                    or any(journal.absolute() == p for p in targets)):
                raise CatalogError("Timing request differs from current inputs")
            self.timing_store = TimingStore(journal, ROOT, value["binding"])
            self.timing_request = value
            self.timing_run = self.timing_store.begin(value["selected"])

        if not config.getoption('collectonly'):
            if self.history_root == ROOT:
                self.history_source = source_identity(ROOT)
            self.history = RuntimeHistory(self.history_root)
            self.history.seed(self.history_root)
            self.history_run = self.history.begin(self.history_source,
                config.getoption('numprocesses', default=0) or 0)

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
    except (CatalogError, OSError, ValueError, sqlite3.Error) as error:
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
    node.workerinput['sr_history_run'] = state.history_run


@pytest.hookimpl(optionalhook=True)
def pytest_xdist_node_collection_finished(node, ids):
    state = node.config._specroad_verification
    state.ledger.collect(node.gateway.id, ids)
    if state.timing_store is not None and set(ids) != set(state.timing_request["selected"]):
        state.timing_store.invalidate(state.timing_run, "collection_mismatch")
        state.ledger.error("timing_collection_mismatch")

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

    def pytest_runtest_logstart(self, nodeid, location):
        state = self.state
        # Persist before test setup in the worker; a killed worker cannot leave
        # a previous successful duration eligible for exclusion.
        if state.history is not None and (state.worker or not state.config.getoption('numprocesses', default=0)):
            state.history.start(state.history_run, nodeid,
                                state.ledger.aliases[nodeid], state.worker_id)

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_logreport(self, report):
        # SubtestReport exposes a context in pytest >=9; do not count its call
        # report as a second execution of the parent test. No output is parsed.
        subtest = hasattr(report, "context")
        if self.state.runtime_measurements is not None:
            self.state.runtime_measurements.observe(report.nodeid, report.when, report.duration, subtest=subtest)
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
        if self.state.timing_store is not None:
            self.state.timing_store.observe(self.state.timing_run, report.nodeid, alias,
                report.when, report.duration, outcome, worker, subtest=subtest)
        state = self.state
        if state.history is not None and (state.worker or not state.config.getoption('numprocesses', default=0)):
            state.history.observe(state.history_run, report.nodeid, alias, worker,
                                  report.when, report.duration, outcome, subtest=subtest)
        self.state.ledger.observe(report.nodeid, worker, report.when, outcome, subtest=subtest)


def pytest_sessionstart(session):
    state = session.config._specroad_verification
    session.config.pluginmanager.register(ReportObserver(state), "specroad-report-observer")


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    state = session.config._specroad_verification
    if state.worker:
        return
    if state.history is not None:
        try:
            changed = state.history_source is not None and source_identity(ROOT) != state.history_source
            if exitstatus == 0 and not state.ledger.errors:
                current = state.ledger.snapshot(exitstatus)
                state.history.verify_run(state.history_run, current['nodeid_to_test_id'], current['test_outcomes'])
            state.history.finish(state.history_run, int(exitstatus), invalid=changed)
            if changed:
                state.ledger.error('runtime_source_changed')
                session.exitstatus = pytest.ExitCode.USAGE_ERROR
        except (OSError, ValueError, sqlite3.Error):
            try:
                state.history.finish(state.history_run, int(pytest.ExitCode.USAGE_ERROR), invalid=True)
            except (OSError, ValueError, sqlite3.Error):
                pass
            state.ledger.error('runtime_storage_failed')
            session.exitstatus = pytest.ExitCode.USAGE_ERROR
        finally:
            state.history.close()
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

    if state.timing_store is not None:
        try:
            if source_identity(ROOT) != state.timing_request["binding"]["source_sha256"]:
                state.timing_store.invalidate(state.timing_run, "source_changed")
                session.exitstatus = pytest.ExitCode.USAGE_ERROR
            state.timing_store.finish(state.timing_run)
        finally:
            state.timing_store.close()

    if state.runtimes is not None:
        try:
            if session.exitstatus != 0 or source_identity(ROOT) != state.source:
                raise ValueError("Only an unchanged successful full run can be calibrated")
            timings = state.runtime_measurements.finish(observation, state.source)
            publish_report(state.runtimes, ROOT, timings)
        except (CatalogError, OSError, ValueError, TypeError, KeyError):
            print("Complete runtime calibration was not published.", file=sys.stderr)
            session.exitstatus = pytest.ExitCode.USAGE_ERROR


def pytest_unconfigure(config):
    state = getattr(config, "_specroad_verification", None)
    if state is not None and state.timing_store is not None:
        state.timing_store.close()
    if state is not None and state.history is not None:
        state.history.close()
