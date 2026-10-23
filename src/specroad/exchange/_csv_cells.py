"""Explicit, loss-rejecting CSV cell conversions using native JSON semantics."""
import re

from ..mappings.csv_profile import CSVError
from ..model.canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object

MISSING = object()
_INTEGER = re.compile(r"-?(0|[1-9][0-9]*)")
_NUMBER = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?")


def _json(text):
    # Reuse the strict native reader for all values, including scalar tokens.
    # Exact wrapper shape also rejects an injected sibling member.
    value = parse_json_object(b'{"value":' + text.encode("utf-8") + b'}')
    if set(value) != {"value"}:
        raise CSVError("csv_json_cell_required")
    return value["value"]


def _kind(value):
    if value is None:
        return "null"
    return {bool: "boolean", int: "number", float: "number", str: "string",
            list: "array", dict: "object"}.get(type(value))


def decode_cell(text, rule):
    if not text:
        if rule["empty_cell"] == "null":
            return None
        if rule["empty_cell"] == "error":
            raise CSVError("csv_empty_cell")
    kind = rule["codec"]["kind"]
    if kind == "string":
        return text
    if kind == "boolean":
        if text not in ("true", "false"):
            raise CSVError("csv_boolean_required")
        return text == "true"
    if kind in ("integer", "number"):
        if (_INTEGER if kind == "integer" else _NUMBER).fullmatch(text) is None:
            raise CSVError("csv_number_required")
        return _json(text)
    value = _json(text)
    if kind == "list":
        if type(value) is not list:
            raise CSVError("csv_array_required")
        return value
    if type(value) is dict and value == {"type": "missing"}:
        return MISSING
    if (type(value) is not dict or set(value) != {"type", "value"}
            or value["type"] != _kind(value["value"])):
        raise CSVError("csv_typed_value_required")
    return value["value"]


def encode_cell(value, rule):
    kind = rule["codec"]["kind"]
    if value is MISSING:
        if kind != "typed-json-v1":
            raise CSVError("csv_missing_unrepresentable")
        return '{"type":"missing"}'
    if value is None and rule["empty_cell"] == "null":
        return ""
    if kind == "typed-json-v1":
        tag = _kind(value)
        if tag is None:
            raise CSVError("csv_typed_value_required")
        text = canonical_json_bytes({"type": tag, "value": value}).decode("utf-8")
    else:
        allowed = {"string": (str,), "boolean": (bool,), "integer": (int,),
                   "number": (int, float), "list": (list,)}[kind]
        if type(value) not in allowed:
            raise CSVError("csv_value_type")
        text = value if kind == "string" else canonical_json_bytes(value).decode("utf-8")
        # JCS can spell large exact integers with an exponent. Integer cells
        # require the integer grammar; canonical validation still applies.
        if kind == "integer":
            text = str(value)
    decoded = decode_cell(text, rule)
    if (_kind(value) != _kind(decoded)
            or canonical_json_bytes(value) != canonical_json_bytes(decoded)):
        raise CSVError("csv_value_unrepresentable")
    return text
