"""Validated immutable expression data; no operator execution."""

from dataclasses import dataclass
from ._json_values import JsonSnapshot
from .validation import _rule_id, _validate_document
from .errors import SrxError
from .resources import StructureLimits, SrxResourcePolicyError

@dataclass(frozen=True, init=False)
class SrxProgram:
    rule_id: str
    _snapshot: JsonSnapshot
    source_bytes: bytes | None
    structure_limits: StructureLimits
    structure: object

    def __init__(self, document, *, rule_id, structure_limits=None):
        rule_id = _rule_id(rule_id)
        limits = StructureLimits() if structure_limits is None else structure_limits
        if type(limits) is not StructureLimits:
            raise SrxResourcePolicyError(rule_id=rule_id, pointer="/structure")
        # Reject executable structure before copying it. Inputs must remain
        # stable during construction; this is not a concurrent-memory sandbox.
        _validate_document(document, rule_id, structure_limits=limits)
        snapshot = JsonSnapshot(document, rule_id=rule_id)
        data = snapshot.data
        structure = _validate_document(data, rule_id, structure_limits=limits)
        object.__setattr__(self, "structure_limits", limits)
        object.__setattr__(self, "structure", structure)
        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "source_bytes", None)
        object.__setattr__(self, "_snapshot", snapshot)

    @property
    def document(self):
        return self._snapshot.data

    @property
    def value(self):
        expression = self.expression
        if expression["op"] != "literal":
            raise SrxError("literal_value_required", rule_id=self.rule_id,
                           expected="literal expression", actual="contextual expression")
        return expression["value"]

    @property
    def expression(self):
        return self._snapshot.data["expression"]


