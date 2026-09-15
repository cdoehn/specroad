"""Real framework integration; inspect outcomes and files, never terminal text."""

from support.pytest_process import run_pytest_fixture


PASSING = """
import unittest
import pytest

class ExistingTests(unittest.TestCase):
    def test_existing(self):
        for value in range(3):
            with self.subTest(value=value):
                self.assertLess(value, 3)

@pytest.mark.parametrize('number', range(4))
def test_native(number):
    assert number >= 0
"""

FAILING = """
import unittest
import pytest

@pytest.fixture
def bad_setup():
    raise ValueError('fixture setup')

@pytest.fixture
def bad_teardown():
    yield
    raise ValueError('fixture cleanup')

def test_setup(bad_setup):
    pass

def test_teardown(bad_teardown):
    pass

@pytest.mark.skip(reason='deliberately exercise outcome accounting')
def test_skip():
    pass

@pytest.mark.xfail(reason='deliberately exercise outcome accounting')
def test_xfail():
    assert False

@pytest.mark.xfail(reason='deliberately exercise outcome accounting')
def test_xpass():
    assert True

class ExistingTests(unittest.TestCase):
    def test_failed_subtest(self):
        with self.subTest(value=1):
            self.assertEqual(1, 2)
        with self.subTest(value=2):
            self.assertEqual(2, 2)
    def test_skipped_subtest(self):
        with self.subTest(value=1):
            self.skipTest('exercise nonpassing subtest')
"""


def test_serial_framework_preserves_legacy_and_native_identities():
    code, observation = run_pytest_fixture(PASSING)
    assert code == 0
    assert observation["suite_passed"]
    assert observation["tests_run"] == 5
    assert "test_subject.ExistingTests.test_existing" in observation["test_outcomes"]
    assert all(value == "passed" for value in observation["test_outcomes"].values())


def test_serial_framework_records_errors_skips_expected_and_subtest_failures():
    code, observation = run_pytest_fixture(FAILING)
    assert code != 0
    assert not observation["suite_passed"]
    outcomes = observation["test_outcomes"]
    assert observation["tests_run"] == 7
    assert outcomes["test_subject.py::test_setup"] == "error"
    assert outcomes["test_subject.py::test_teardown"] == "error"
    assert outcomes["test_subject.py::test_skip"] == "skipped"
    assert outcomes["test_subject.py::test_xfail"] == "expected_failure"
    assert outcomes["test_subject.py::test_xpass"] == "unexpected_success"
    assert outcomes["test_subject.ExistingTests.test_failed_subtest"] == "failed"
    assert outcomes["test_subject.ExistingTests.test_skipped_subtest"] == "skipped"


def test_collection_error_never_yields_success():
    code, observation = run_pytest_fixture("raise RuntimeError('broken collection')\n")
    assert code != 0
    assert observation is not None
    assert not observation["suite_passed"]
    assert "collection_error" in observation["errors"]


def test_gate_rejects_subsets_even_when_tests_themselves_pass():
    code, observation = run_pytest_fixture(PASSING, gate=True)
    assert code != 0
    assert observation is None or not observation["suite_passed"]


def test_parallel_framework_matches_serial_test_identities():
    serial_code, serial = run_pytest_fixture(PASSING)
    parallel_code, parallel = run_pytest_fixture(PASSING, workers="2")
    assert serial_code == parallel_code == 0
    assert serial["suite_passed"] and parallel["suite_passed"]
    assert serial["test_outcomes"] == parallel["test_outcomes"]
    assert serial["nodeids"] == parallel["nodeids"]
    assert parallel["tests_run"] == 5
    assert len([count for count in parallel["worker_test_counts"].values() if count > 0]) == 2


def test_parallel_framework_transports_failures_and_subtest_outcomes():
    serial_code, serial = run_pytest_fixture(FAILING)
    parallel_code, parallel = run_pytest_fixture(FAILING, workers="2")
    assert serial_code != 0 and parallel_code != 0
    assert not parallel["suite_passed"]
    assert serial["test_outcomes"] == parallel["test_outcomes"]
    assert serial["tests_run"] == parallel["tests_run"] == 7


def test_crashed_worker_never_produces_success():
    source = "import os\n\ndef test_crash():\n    os._exit(17)\n\ndef test_other():\n    pass\n"
    code, observation = run_pytest_fixture(source, workers="2")
    assert code != 0
    assert observation is not None
    assert not observation["suite_passed"]
    assert "worker_crash" in observation["errors"]


def test_workers_with_different_collections_fail():
    source = """
import os
if os.environ.get('PYTEST_XDIST_WORKER') == 'gw0':
    def test_first():
        pass
else:
    def test_second():
        pass
"""
    code, observation = run_pytest_fixture(source, workers="2")
    assert code != 0
    assert observation is not None
    assert not observation["suite_passed"]
    assert "inconsistent_worker_collection" in observation["errors"]


def test_two_independent_parallel_sessions_do_not_share_artifacts():
    first_code, first = run_pytest_fixture(PASSING, workers="2")
    second_code, second = run_pytest_fixture(PASSING, workers="2")
    assert first_code == second_code == 0
    assert first["suite_passed"] and second["suite_passed"]
    assert first["test_outcomes"] == second["test_outcomes"]


def test_parallel_collection_failure_is_not_an_empty_success():
    code, observation = run_pytest_fixture("raise ValueError('fixture collection failure')\n", workers="2")
    assert code != 0
    assert observation is not None
    assert not observation["suite_passed"]
