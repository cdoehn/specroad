"""Sequential RFC-6902 on isolated JSON values; no artifact or CLI policy."""
from __future__ import annotations
from dataclasses import dataclass
import re
from ..srx._json_values import JsonSnapshot
from ..srx.comparisons import _equal
from ._patch_values import JsonPatchError, _snapshot, _tokens, _raw_value


@dataclass(frozen=True, init=False)
class JsonPatch:
    """Owned RFC-6902 operations. Unknown operation members remain passive."""
    _value: JsonSnapshot
    source_bytes: bytes | None

    def __init__(self, operations):
        owned = _snapshot(operations, "/patch")
        data = owned.data
        if type(data) is not list:
            raise JsonPatchError("patch_array_required", pointer="/patch")
        for index, item in enumerate(data):
            at = "/patch/" + str(index)
            if type(item) is not dict:
                raise JsonPatchError("operation_object_required", pointer=at, operation_index=index)
            if type(item.get("op")) is not str or item["op"] not in ("add", "remove", "replace", "move", "copy", "test"):
                raise JsonPatchError("unknown_patch_operation", pointer=at + "/op", operation_index=index)
            _tokens(item.get("path"), at + "/path")
            if item["op"] in ("add", "replace", "test") and "value" not in item:
                raise JsonPatchError("patch_value_required", pointer=at + "/value", operation_index=index)
            if item["op"] in ("move", "copy"):
                _tokens(item.get("from"), at + "/from")
        object.__setattr__(self, "_value", owned)
        object.__setattr__(self, "source_bytes", None)

    @classmethod
    def from_bytes(cls, raw):
        """Parse supplied bytes only; never interpret text as a file to open."""
        operations = _raw_value(raw, "/patch")
        result = cls(operations)
        object.__setattr__(result, "source_bytes", raw)
        return result

    @property
    def data(self):
        return self._value.data

    def apply(self, document):
        return apply_json_patch(document, self)


@dataclass(frozen=True)
class PatchResult:
    """A removed root is absent, not JSON null. Returned data is always detached."""
    _value: JsonSnapshot | None
    operations_applied: int

    @property
    def document_exists(self):
        return self._value is not None

    @property
    def data(self):
        if self._value is None:
            raise JsonPatchError("document_absent")
        return self._value.data

    @property
    def write_authorized(self):
        return False

    @property
    def validation_scope(self):
        return "json_patch_values_only"


_ABSENT = object()


def _index(token, size, *, insert, fail):
    if token == "-" and insert:
        return size
    if not re.fullmatch(r"0|[1-9][0-9]*", token):
        fail("invalid_array_index")
    # Compare lengths before converting: no Python digit-limit failure, even
    # for a hostile multi-thousand-digit index. Object keys are not indices.
    limit = size if insert else size - 1
    bound = str(limit)
    if limit < 0 or len(token) > len(bound) or (len(token) == len(bound) and token > bound):
        fail("array_index_out_of_bounds")
    return int(token)


def _read(document, tokens, fail):
    value = document
    if value is _ABSENT:
        fail("document_absent")
    for token in tokens:
        if type(value) is dict:
            if token not in value:
                fail("pointer_missing")
            value = value[token]
        elif type(value) is list:
            value = value[_index(token, len(value), insert=False, fail=fail)]
        else:
            fail("pointer_parent_not_container")
    return value


def _write(document, tokens, kind, value, fail):
    if not tokens:
        if kind != "add" and document is _ABSENT:
            fail("document_absent")
        return _ABSENT if kind == "remove" else value
    parent = _read(document, tokens[:-1], fail)
    key = tokens[-1]
    if type(parent) is dict:
        if kind != "add" and key not in parent:
            fail("pointer_missing")
        if kind == "remove":
            del parent[key]
        else:
            parent[key] = value
    elif type(parent) is list:
        index = _index(key, len(parent), insert=kind == "add", fail=fail)
        if kind == "add":
            parent.insert(index, value)
        elif kind == "remove":
            del parent[index]
        else:
            parent[index] = value
    else:
        fail("pointer_parent_not_container")
    return document


def _apply_one(document, item, index):
    at = "/patch/" + str(index)
    tokens = _tokens(item["path"], at + "/path")

    def fail(reason, member="path"):
        raise JsonPatchError(reason, pointer=at + "/" + member,
                             operation_index=index, document_pointer=item.get(member))

    kind = item["op"]
    if kind == "test":
        actual = _read(document, tokens, fail)
        if not _equal(actual, item["value"]):
            fail("test_failed")
        return document
    if kind in ("move", "copy"):
        source = _tokens(item["from"], at + "/from")
        if kind == "move" and len(tokens) > len(source) and tokens[:len(source)] == source:
            fail("move_into_descendant", "from")
        value = _read(document, source, lambda reason: fail(reason, "from"))
        # Copy must not alias its source (including copy to a descendant).
        if kind == "copy":
            value = _snapshot(value).data
        else:
            if source == tokens:
                return document  # Still requires the source to exist.
            document = _write(document, source, "remove", None, lambda reason: fail(reason, "from"))
        return _write(document, tokens, "add", value, fail)
    value = _snapshot(item["value"]).data if "value" in item and kind in ("add", "replace") else None
    return _write(document, tokens, kind, value, fail)


def apply_json_patch(document, patch):
    """Apply sequentially on one private copy; an error returns no partial result.

    This pure value engine is not an artifact writer, schema validator or
    lifecycle/identity authorization path. Use preview_update for artifacts.
    """
    program = patch if type(patch) is JsonPatch else JsonPatch(patch)
    current = _snapshot(document, "/document").data
    operations = program.data
    for index, item in enumerate(operations):
        current = _apply_one(current, item, index)
    return PatchResult(None if current is _ABSENT else _snapshot(current), len(operations))
