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
