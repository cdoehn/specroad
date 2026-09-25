"""Owned immutable JSON values: no live-state checks and no I/O."""
from dataclasses import dataclass
from ..model.canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object
from ._common import _at
from .operation_registry import (validate_operation as _validate_operation,
    result_owners as _targets, required_workflow)
from .plan_contract import _validate_plan
from .errors import ChangePlanError

@dataclass(frozen=True, init=False)
class ChangeOperation:
    """Immutable tagged operation data. Its workflow name is not authorization."""
    _encoded: bytes

    def __init__(self, value):
        encoded = _at("", canonical_json_bytes, value)
        owned = _at("", parse_json_object, encoded)
        _validate_operation(owned)
        object.__setattr__(self, "_encoded", encoded)

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def op(self):
        return self.data["op"]

    @property
    def required_workflow(self):
        return required_workflow(self.op)

    @property
    def result_ids(self):
        return _targets(self.data)

    @property
    def executable(self):
        return False

@dataclass(frozen=True, init=False)
class ChangePlan:
    """A byte-preserving parsed plan, NOT a checked live-state or write ticket."""
    source_bytes: bytes
    _encoded: bytes

    def __init__(self, raw):
        if type(raw) is not bytes:
            raise ChangePlanError("bytes_required")
        value = _at("", parse_json_object, raw)
        _validate_plan(value)
        object.__setattr__(self, "source_bytes", raw)
        object.__setattr__(self, "_encoded", _at("", canonical_json_bytes, value))

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def canonical_bytes(self):
        return self._encoded

    @property
    def sha256(self):
        return self.data["change_plan_sha256"]

    @property
    def operations(self):
        return tuple(ChangeOperation(item) for item in self.data["operations"])

    @property
    def validation_scope(self):
        return "change_plan_fields_only"

    @property
    def write_authorized(self):
        return False

    @property
    def execution_ready(self):
        return False

