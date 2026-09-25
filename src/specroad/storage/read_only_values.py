"""Owned report values. Neither a source handle nor a write-authorization type."""
from __future__ import annotations
from dataclasses import dataclass
from ..model.canonical import canonical_json_bytes
from .json_syntax import parse_json_object

READ_ONLY_VERSION = "project-read-only-v1"

@dataclass(frozen=True, init=False)
class ReadOnlyResult:
    """Detached report, never a permission to publish or a whole-project approval."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError("Use the project read-only entry functions")

    @classmethod
    def _create(cls, value):
        result = object.__new__(cls)
        object.__setattr__(result, "_encoded", canonical_json_bytes(value))
        return result

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def passed(self):
        return self.data["passed"] is True

    @property
    def exit_code(self):
        return self.data["exit_code"]

    def __bool__(self):
        raise TypeError("Use result.passed explicitly")


