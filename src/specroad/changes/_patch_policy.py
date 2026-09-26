"""Controlled artifact fields, independent of patch execution and CLI input."""
from ..model.record_contracts import SPECIAL_STATES
from .errors import ChangePlanError
from ._patch_pointer import _pointer

_CONTROLLED = frozenset({"id", "id_scheme", "artifact_type", "schema_version", "maturity", "revision",
    "created_at", "created_by", "updated_at", "updated_by", "relations"})


def _mutable_pointer(value, pointer):
    parts = _pointer(value, pointer)
    if not parts or parts[0] in _CONTROLLED or parts[0] in {v[0] for v in SPECIAL_STATES.values()}:
        raise ChangePlanError("controlled_field_mutation", pointer=pointer)


def _patch(items, pointer):
    for index, item in enumerate(items):
        at = pointer + "/" + str(index)
        _pointer(item["path"], at + "/path")
        if item["op"] != "test":
            _mutable_pointer(item["path"], at + "/path")
        if item["op"] in ("move", "copy"):
            _pointer(item["from"], at + "/from")
            if item["op"] == "move":
                _mutable_pointer(item["from"], at + "/from")
