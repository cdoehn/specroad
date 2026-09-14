"""The dependency-free SpecRoad Core. No project is loaded on import."""

from ._metadata import MINIMUM_PYTHON, __version__
from .runtime import UnsupportedRuntimeError, check_runtime

__all__ = ["MINIMUM_PYTHON", "UnsupportedRuntimeError", "__version__", "check_runtime"]

check_runtime()
