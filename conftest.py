"""Project test bootstrap; not imported by the SpecRoad Core."""

import sys

# Tests inspect real filesystem effects; bytecode is not part of the fixtures.
sys.dont_write_bytecode = True

import pytest
from support.isolation import ProcessState


@pytest.fixture(autouse=True)
def isolated_test_process():
    state = ProcessState()
    yield
    leaked = state.restore()
    if leaked:
        pytest.fail("Test leaked process state: " + ", ".join(leaked), pytrace=False)

pytest_plugins = ("verification_support.pytest_backend",)
