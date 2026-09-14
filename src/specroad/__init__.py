"""The dependency-free SpecRoad Core. No project is loaded on import."""

import sys

__version__ = "0.2.0.dev0"
MINIMUM_PYTHON = (3, 10)


class UnsupportedRuntimeError(RuntimeError):
    """The interpreter cannot run the SpecRoad Core."""


def check_runtime() -> None:
    """Validate the interpreter without I/O, installation or shell calls."""
    if sys.implementation.name != "cpython" or sys.version_info[:2] < MINIMUM_PYTHON:
        raise UnsupportedRuntimeError("SpecRoad requires CPython 3.10 or newer.")


check_runtime()
