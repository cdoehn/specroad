"""Validated immutable expression data; no operator execution."""

from dataclasses import dataclass
from ._json_values import JsonSnapshot
from .validation import _rule_id, _validate_document

@dataclass(frozen=True, init=False)
class SrxProgram:
    rule_id: str
    _snapshot: JsonSnapshot
    _value: JsonSnapshot
    source_bytes: bytes | None

    def __init__(self, document, *, rule_id):
        rule_id = _rule_id(rule_id)
        snapshot = JsonSnapshot(document, rule_id=rule_id)
        data = snapshot.data
        _validate_document(data, rule_id)
        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "source_bytes", None)
        object.__setattr__(self, "_snapshot", snapshot)
        object.__setattr__(self, "_value", JsonSnapshot(data["expression"]["value"],
                                                     rule_id=rule_id, pointer="/expression/value"))

    @property
    def document(self):
        return self._snapshot.data

    @property
    def value(self):
        return self._value.data


