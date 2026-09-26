"""JSON Patch on owned values; never mutate inputs or publish project files.

The generic engine has no artifact policy. Artifact callers must use
preview_update, which enforces the existing controlled-field and identity gates.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
from ..srx._json_values import JsonSnapshot
from ..srx.comparisons import _equal
from ..srx.errors import SrxError
from ..storage.json_syntax import parse_json_object
from ..model.errors import ModelError
from ..model.canonical import canonical_json_sha256
from .errors import ChangePlanError
from .values import ChangeOperation
from ._common import _pointer, _mutable_pointer, _artifact, _generic, _at


class JsonPatchError(ChangePlanError):
    """A structured operation failure, with no submitted values in diagnostics."""

    def __init__(self, reason, *, pointer="", operation_index=None, document_pointer=None):
        super().__init__(reason, pointer=pointer)
        self.operation_index = operation_index
        self.document_pointer = document_pointer

    def diagnostic(self):
        return {**super().diagnostic(), "operation_index": self.operation_index,
                "document_pointer": self.document_pointer}


def _snapshot(value, pointer=""):
    # Reuse the existing iterative JSON value boundary, not copy/deepcopy hooks.
    try:
        return JsonSnapshot(value, rule_id="json-patch-values", pointer=pointer)
    except SrxError as error:
        raise JsonPatchError(error.reason, pointer=error.pointer) from None


def _tokens(value, at):
    try:
        return tuple(_pointer(value, at))
    except ChangePlanError as error:
        raise JsonPatchError(error.reason, pointer=at) from None


@dataclass(frozen=True, init=False)
class JsonPatch:
    """Owned RFC-6902 operations. Unknown operation members remain passive."""
    _value: JsonSnapshot

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


def _strict_value(text, at):
    if type(text) is not str:
        raise JsonPatchError("json_text_required", pointer=at)
    try:
        # The strict existing object reader supplies duplicate-key, Unicode and
        # decimal-roundtrip checks. The closed wrapper rejects injected siblings.
        raw = text.encode("utf-8")
        parsed = parse_json_object(b'{"value":' + raw + b'}')
        if set(parsed) != {"value"}:
            raise JsonPatchError("one_json_value_required", pointer=at)
        return parsed["value"]
    except (ModelError, UnicodeError) as error:
        raise JsonPatchError("invalid_json_value", pointer=at) from None


def compile_field_patch(document, options):
    """Convert ordered (--set, pointer=JSON) / (--unset, pointer) pairs.

    Set replaces an existing array slot; it never inserts there. A missing object
    member is added. '-' or the array's exact length appends; holes are errors.
    No implicit parents, unquoted strings, shell expansion or schema defaults.
    """
    if type(options) not in (list, tuple):
        raise JsonPatchError("ordered_options_required", pointer="/options")
    current = _snapshot(document, "/document").data
    operations = []
    for index, pair in enumerate(options):
        at = "/options/" + str(index)
        if type(pair) not in (list, tuple) or len(pair) != 2 or any(type(v) is not str for v in pair):
            raise JsonPatchError("option_pair_required", pointer=at)
        option, argument = pair
        if option == "--set":
            pointer, separator, text = argument.partition("=")
            if not separator:
                raise JsonPatchError("set_assignment_required", pointer=at)
            value = _strict_value(text, at)
            tokens = _tokens(pointer, at)
            def fail(reason):
                raise JsonPatchError(reason, pointer=at, document_pointer=pointer)
            if not tokens:
                kind = "replace"
            else:
                parent = _read(current, tokens[:-1], fail)
                key = tokens[-1]
                if type(parent) is dict:
                    kind = "replace" if key in parent else "add"
                elif type(parent) is list:
                    position = _index(key, len(parent), insert=True, fail=fail)
                    kind = "add" if position == len(parent) else "replace"
                else:
                    fail("pointer_parent_not_container")
            item = {"op": kind, "path": pointer, "value": value}
        elif option == "--unset":
            item = {"op": "remove", "path": argument}
            _tokens(argument, at)
        else:
            raise JsonPatchError("unknown_field_option", pointer=at)
        # Execute the actual normalized operations, so later options see the
        # exact preceding values. No dictionary merge or reordering of flags.
        current = _apply_one(current, item, index)
        operations.append(item)
    return JsonPatch(operations)


@dataclass(frozen=True)
class UpdatePreview:
    """Candidate field values, without revision advancement or publication."""
    operation: ChangeOperation
    _candidate: JsonSnapshot
    base_sha256: str
    candidate_sha256: str

    @property
    def candidate(self):
        return self._candidate.data

    @property
    def changed(self):
        return self.base_sha256 != self.candidate_sha256

    @property
    def metadata_applied(self):
        return False

    @property
    def write_authorized(self):
        return False

    @property
    def validation_scope(self):
        return "update_candidate_only"


def preview_update(artifact, operation):
    """Check target/preconditions and protected fields, then isolate one update.

    Expected revision OR canonical artifact hash is mandatory; when both are
    present both must match. No current revision/time/user is invented. Checking
    supplied values is not an atomic live-storage check or proposal authorization.
    """
    current = _snapshot(artifact, "/artifact").data
    identity = _artifact(current, "/artifact")
    _generic(identity, "/artifact")
    op = operation if type(operation) is ChangeOperation else ChangeOperation(operation)
    value = op.data
    if value["op"] != "update":
        raise ChangePlanError("update_operation_required", pointer="/op")
    if value["target"] != identity.id:
        raise ChangePlanError("update_target_mismatch", pointer="/target", code="SRV146")
    before = _at("/artifact", canonical_json_sha256, current)
    if "expected_revision" in value and value["expected_revision"] != current["revision"]:
        raise ChangePlanError("expected_revision_mismatch", pointer="/expected_revision", code="SRV146")
    if "expected_sha256" in value and value["expected_sha256"] != before:
        raise ChangePlanError("expected_hash_mismatch", pointer="/expected_sha256", code="SRV146")
    # ChangeOperation already validates controlled destinations and move sources.
    result = apply_json_patch(current, value["patch"])
    candidate = result.data
    _artifact(candidate, "/candidate", expected_type=identity.artifact_type)
    after = _at("/candidate", canonical_json_sha256, candidate)
    return UpdatePreview(op, _snapshot(candidate), before, after)
