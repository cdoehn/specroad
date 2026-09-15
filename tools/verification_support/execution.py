"""Developer verification: execution responsibilities."""

import unittest
from .common import CatalogError


def flatten_suite(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from flatten_suite(test)
        else:
            yield test


def bind_tests(catalog, suite):
    tests = list(flatten_suite(suite))
    ids = [test.id() for test in tests]
    if not ids or len(ids) != len(set(ids)):
        raise CatalogError("Test discovery is empty or ambiguous")
    available = set(ids)
    for case in catalog.cases:
        if not set(case.data["test_ids"]) <= available:
            raise CatalogError("Manifest names an unavailable real test: " + case.data["test_case_id"])
    return tuple(ids)


class ObservedResult(unittest.TextTestResult):
    """Record actual unittest callbacks, including non-passing subtests."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes = {}

    def startTest(self, test):
        super().startTest(test)
        self.outcomes[test.id()] = "running"

    def _record(self, test, state):
        key = getattr(test, "test_case", test).id()
        rank = {"running": 0, "passed": 1, "expected_failure": 2, "skipped": 3,
                "unexpected_success": 4, "failed": 5, "error": 6}
        previous = self.outcomes.get(key, "running")
        if rank[state] > rank[previous]:
            self.outcomes[key] = state

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "passed")

    def addError(self, test, error):
        super().addError(test, error)
        self._record(test, "error")

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self._record(test, "failed")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "skipped")

    def addExpectedFailure(self, test, error):
        super().addExpectedFailure(test, error)
        self._record(test, "expected_failure")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._record(test, "unexpected_success")

    def addSubTest(self, test, subtest, error):
        super().addSubTest(test, subtest, error)
        if error is not None:
            self._record(test, "failed" if issubclass(error[0], test.failureException) else "error")


def observe_suite(suite, *, stream=None, verbosity=2):
    return unittest.TextTestRunner(stream=stream, verbosity=verbosity,
                                  resultclass=ObservedResult).run(suite)


