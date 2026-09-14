"""Interpreter prerequisites, independent of CLI and project state."""

import sys

from .._metadata import MINIMUM_PYTHON


class UnsupportedRuntimeError(RuntimeError):
    """The interpreter cannot run the SpecRoad Core."""


def check_runtime() -> None:
    """Validate the interpreter without I/O, installation or shell calls."""
    if sys.implementation.name != "cpython" or sys.version_info[:2] < MINIMUM_PYTHON:
        raise UnsupportedRuntimeError("SpecRoad requires CPython 3.10 or newer.")
