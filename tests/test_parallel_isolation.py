"""Behavior of the process boundary shared by serial and xdist execution."""

import os
from pathlib import Path
import random
import sys

from support import temporary_project
from support.isolation import ProcessState
from support.portable import build_distribution


def test_unchanged_state_needs_no_repair():
    assert ProcessState().restore() == ()


def test_environment_is_restored_without_exposing_its_contents():
    state = ProcessState()
    try:
        os.environ["SPECRD_ISOLATION_SENTINEL"] = "private-value"
    finally:
        changed = state.restore()
    assert changed == ("environment",)
    assert dict(os.environ).get("SPECRD_ISOLATION_SENTINEL") == state.environment.get("SPECRD_ISOLATION_SENTINEL")


def test_working_directory_is_restored():
    with temporary_project() as root:
        state = ProcessState()
        try:
            os.chdir(root)
        finally:
            assert state.restore() == ("cwd",)
        assert os.getcwd() == state.cwd


def test_import_path_is_restored():
    state = ProcessState()
    try:
        sys.path.append("not-an-import-location")
    finally:
        assert state.restore() == ("sys.path",)
    assert sys.path == state.path


def test_random_state_is_restored():
    state = ProcessState()
    try:
        random.seed(987654321)
    finally:
        assert state.restore() == ("random",)
    assert random.getstate() == state.random


def test_framework_current_test_marker_is_not_treated_as_user_state():
    previous = os.environ.get("PYTEST_CURRENT_TEST")
    state = ProcessState()
    try:
        os.environ["PYTEST_CURRENT_TEST"] = "framework-controlled-marker"
        assert state.restore() == ()
    finally:
        if previous is None:
            os.environ.pop("PYTEST_CURRENT_TEST", None)
        else:
            os.environ["PYTEST_CURRENT_TEST"] = previous


def test_repeated_build_fixture_does_not_change_import_path():
    previous = list(sys.path)
    with temporary_project() as root:
        build_distribution(root / "first")
        build_distribution(root / "second")
    assert sys.path == previous


def test_removed_working_directory_is_restored():
    import os
    import tempfile
    from pathlib import Path
    state = ProcessState()
    with tempfile.TemporaryDirectory(prefix="specroad-deleted-cwd-") as directory:
        path = Path(directory) / "removed"
        path.mkdir()
        try:
            os.chdir(path)
            path.rmdir()
            assert state.restore() == ("cwd",)
            assert os.getcwd() == state.cwd
        finally:
            os.chdir(state.cwd)
