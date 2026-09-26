"""Owned patch values and raw decoding, independent of artifact policy."""
from ..srx._json_values import JsonSnapshot
from ..srx.errors import SrxError
from ..storage.json_syntax import parse_json_object
from ..model.errors import ModelError
from .errors import ChangePlanError
from ._patch_pointer import _pointer


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


def _raw_value(raw, at):
    if type(raw) is not bytes:
        raise JsonPatchError("bytes_required", pointer=at)
    try:
        raw.decode("utf-8")
        parsed = parse_json_object(b'{"value":' + raw + b'}')
    except (ModelError, UnicodeError) as error:
        reason = error.reason if isinstance(error, ModelError) else "invalid_utf8"
        pointer = getattr(error, "pointer", "")
        pointer = at + pointer[len("/value"):] if pointer == "/value" or pointer.startswith("/value/") else at
        # The object reader's wrapper-relative coordinates are deliberately not
        # passed off as coordinates in the original input byte sequence.
        raise JsonPatchError(reason, pointer=pointer) from None
    if set(parsed) != {"value"}:
        raise JsonPatchError("one_json_value_required", pointer=at)
    return parsed["value"]


def _strict_value(text, at):
    if type(text) is not str:
        raise JsonPatchError("json_text_required", pointer=at)
    try:
        raw = text.encode("utf-8")
    except UnicodeError:
        raise JsonPatchError("invalid_unicode", pointer=at) from None
    return _raw_value(raw, at)
